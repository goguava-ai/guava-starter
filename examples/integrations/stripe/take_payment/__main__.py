# SDK conformance: guava-sdk 0.34.0 (2026-07-14)
"""Inbound pay-by-phone demo using a Stripe Checkout link sent over SMS.

What the caller experiences:
  1. They call our Guava number.
  2. Grace (the Guava agent) greets them and asks how much they want to pay.
  3. They confirm; Grace texts them a Stripe Checkout link.
  4. They tap the link and enter their card details on Stripe's hosted page.
  5. As soon as Stripe reports the payment as paid, Grace voice-confirms and hangs up.

Required environment variables:
  STRIPE_SECRET_KEY   Stripe API key (use sk_test_... for demos)
  GUAVA_AGENT_NUMBER  The phone number the agent listens on, used as SMS sender
"""

import argparse
import logging
import os
import threading
import time
from typing import Optional

import guava
import requests
from guava import logging_utils
from guava.types.call_info import PSTNCallInfo


# ------------------------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------------------------

# Stripe uses HTTP Basic auth with the secret key as the username and an empty password.
STRIPE_SECRET_KEY = os.environ["STRIPE_SECRET_KEY"]
STRIPE_AUTH = (STRIPE_SECRET_KEY, "")
STRIPE_BASE_URL = "https://api.stripe.com"

# Stripe Checkout requires success/cancel URLs even though the caller never sees them
# (they get the voice confirmation instead). Override via env for a branded landing page.
SUCCESS_URL = os.environ.get("PAYMENT_SUCCESS_URL", "https://goguava.ai")
CANCEL_URL = os.environ.get("PAYMENT_CANCEL_URL", "https://goguava.ai")

# How long to keep the call alive while waiting for the caller to complete payment.
POLL_INTERVAL_SECONDS = 2
POLL_TIMEOUT_SECONDS = 180

# Shared Guava client — used for sending the SMS.
client = guava.Client()


# ------------------------------------------------------------------------------------
# Stripe API helpers
# ------------------------------------------------------------------------------------
# Stripe expects form-encoded bodies (`data=...`), not JSON. Brackets in keys nest
# fields, e.g. `line_items[0][price_data][currency]`.

def create_checkout_session(amount_cents: int, description: str) -> dict:
    """Creates a one-shot Stripe Checkout Session. The response includes the hosted URL."""
    resp = requests.post(
        f"{STRIPE_BASE_URL}/v1/checkout/sessions",
        auth=STRIPE_AUTH,
        data={
            "mode": "payment",
            "line_items[0][price_data][currency]": "usd",
            "line_items[0][price_data][product_data][name]": description,
            "line_items[0][price_data][unit_amount]": amount_cents,
            "line_items[0][quantity]": 1,
            "success_url": SUCCESS_URL,
            "cancel_url": CANCEL_URL,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def get_checkout_session(session_id: str) -> dict:
    """Returns the current state of a Checkout Session. We poll this for payment_status."""
    resp = requests.get(
        f"{STRIPE_BASE_URL}/v1/checkout/sessions/{session_id}",
        auth=STRIPE_AUTH,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


# ------------------------------------------------------------------------------------
# Phone-number helpers
# ------------------------------------------------------------------------------------

def caller_number(call: guava.Call) -> Optional[str]:
    """The caller's number from caller-ID, or None for blocked / non-PSTN calls."""
    info = call.call_info
    if isinstance(info, PSTNCallInfo):
        return info.from_number
    return None


def normalize_phone(value: Optional[str]) -> Optional[str]:
    """Best-effort cleanup of a phone number the caller spoke aloud → E.164 (+1...)."""
    if not value:
        return None
    digits = "".join(c for c in value if c.isdigit())
    if not digits:
        return None
    if value.strip().startswith("+"):
        return "+" + digits
    if len(digits) == 10:           # bare US 10-digit
        return "+1" + digits
    return "+" + digits             # 11-digit starting with 1, or anything else


# ------------------------------------------------------------------------------------
# Agent definition + call handlers
# ------------------------------------------------------------------------------------
# Handlers below are listed in the order they fire during a call:
#   on_call_received  → on_call_start  → on_amount_collected  → await_payment

agent = guava.Agent(
    name="Grace",
    organization="Guava Demo Pay",
    purpose="to collect a one-time payment by texting the caller a secure Stripe payment link.",
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    # Accept every inbound call. Return DeclineCall() to reject (e.g. anonymous-only policies).
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    """First voice task: greet, collect the amount, and confirm intent to pay."""

    # If caller-ID is blocked we can't text them — add a question to collect it on the call.
    needs_phone_number = caller_number(call) is None

    checklist: list[guava.Field | guava.Say | str] = [
        guava.Say("Hi, I'm Grace with Guava Demo Pay. I can take a payment for you right now."),
        guava.Field(
            key="amount_dollars",
            field_type="integer",
            description="Ask how many US dollars they'd like to pay today, whole dollars only.",
            required=True,
        ),
    ]
    if needs_phone_number:
        checklist.append(guava.Field(
            key="phone_number",
            field_type="text",
            description=(
                "Ask the caller for the best US mobile number to text the payment link to. "
                "Read it back digit by digit to confirm. "
                "Return the value in E.164 format, e.g. +15551234567."
            ),
            required=True,
        ))
    checklist.append(guava.Field(
        key="confirm_proceed",
        field_type="multiple_choice",
        choices=["yes", "no"],
        description=(
            "Read back the amount and confirm they want to proceed. "
            "Tell them we'll text a secure link to enter their card details."
        ),
        required=True,
    ))

    call.set_task(
        "collect_amount",
        objective=(
            "Greet the caller, collect a payment amount in whole US dollars, "
            "and confirm they want to proceed before we text them a payment link."
        ),
        checklist=checklist,
    )


@agent.on_task_complete("collect_amount")
def on_amount_collected(call: guava.Call) -> None:
    """Fires once the checklist above is filled. Creates a link, texts it, then waits."""

    # --- Did the caller back out? ---------------------------------------------------
    if call.get_field("confirm_proceed") != "yes":
        call.hangup(final_instructions=(
            "Thank the caller politely and let them know no charge was made. "
            "Invite them to call back any time."
        ))
        return

    # --- Where to text the link -----------------------------------------------------
    # Caller-ID first; otherwise whatever the caller told us during the call.
    number = caller_number(call) or normalize_phone(call.get_field("phone_number"))
    if not number:
        call.hangup(final_instructions=(
            "Apologize for a technical issue capturing their phone number. "
            "Let them know no charge was made and suggest they call back or pay on our website."
        ))
        return

    amount_dollars = int(call.get_field("amount_dollars"))

    # --- Create the Stripe Checkout link --------------------------------------------
    try:
        session = create_checkout_session(
            amount_cents=amount_dollars * 100,
            description=f"Phone payment to Guava Demo Pay (${amount_dollars})",
        )
    except Exception:
        logging.exception("Stripe create_checkout_session failed")
        call.hangup(final_instructions=(
            "Apologize for a technical issue creating the payment link. "
            "No charge was made; ask them to try again later."
        ))
        return

    # --- Text the link to the caller ------------------------------------------------
    try:
        client.send_sms(
            from_number=os.environ["GUAVA_AGENT_NUMBER"],
            to_number=number,
            message=(
                f"Your secure Stripe payment link for ${amount_dollars}: {session['url']}\n"
                "Tap to complete payment. We'll confirm on the call."
            ),
        )
    except Exception:
        logging.exception("send_sms to %s failed", number)
        call.hangup(final_instructions=(
            "Apologize that we couldn't text the payment link. "
            "Suggest they pay on our website instead."
        ))
        return

    # --- Keep the agent quietly engaged while the caller pays -----------------------
    # send_instruction nudges the LLM mid-conversation without replacing the current task.
    # We use it here both to set expectations and to tell Grace to stay quiet by default.
    call.send_instruction(
        f"Tell the caller: 'I just texted a secure payment link to your phone for "
        f"${amount_dollars}. Tap it, enter your card details on the Stripe page, and I'll "
        f"confirm here as soon as it goes through. I'll stay on the line.' "
        "If they ask whether the link is safe, reassure them it's hosted by Stripe and we "
        "never see their card details. Otherwise, stay silent until further notice — "
        "the call will close automatically when payment lands."
    )

    # --- Background poll for 'paid' -------------------------------------------------
    # Guava's command queue is thread-safe, so hangup/send_instruction calls from this
    # background thread are safe.
    threading.Thread(
        target=await_payment,
        args=(call, session["id"], amount_dollars),
        daemon=True,
    ).start()


def await_payment(call: guava.Call, session_id: str, amount_dollars: int) -> None:
    """Polls Stripe for payment_status='paid'. On success, expiry, or timeout: hangs up."""

    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        time.sleep(POLL_INTERVAL_SECONDS)

        try:
            session = get_checkout_session(session_id)
        except Exception:
            logging.exception("Polling Checkout Session %s failed", session_id)
            continue  # transient error — keep polling

        if session.get("payment_status") == "paid":
            # First 8 chars of the PaymentIntent id make a tidy human-readable confirmation.
            payment_intent_id = session.get("payment_intent") or session_id
            confirmation = payment_intent_id.split("_", 1)[-1][:8].upper()
            logging.info("Checkout %s paid (PI %s)", session_id, payment_intent_id)
            call.hangup(final_instructions=(
                f"Tell the caller their payment of {amount_dollars} dollars was received. "
                f"Give them confirmation number {confirmation}, spelled letter by letter "
                f"and digit by digit. Thank them warmly and wish them a great day."
            ))
            return

        if session.get("status") == "expired":
            logging.info("Checkout Session %s expired", session_id)
            break  # caller won't be able to pay even if they tap the link now

    logging.info("Checkout Session %s timed out without payment", session_id)
    call.hangup(final_instructions=(
        "Politely let the caller know we haven't seen the payment come through yet. "
        "Tell them the link will stay active and they can complete it any time, "
        "or call back if they'd like to try again. Thank them for their patience."
    ))


# ------------------------------------------------------------------------------------
# Entrypoint
# ------------------------------------------------------------------------------------

if __name__ == "__main__":
    logging_utils.configure_logging()

    parser = argparse.ArgumentParser(
        description="Inbound pay-by-phone demo using a Stripe Checkout link sent over SMS."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--phone",  metavar="PHONE_NUMBER", nargs="?", const="", help="Listen for phone calls.")
    group.add_argument("--webrtc", metavar="WEBRTC_CODE",  nargs="?", const="", help="Listen on a WebRTC code.")
    group.add_argument("--local",  action="store_true",                          help="Start a local call.")
    group.add_argument("--sip",    metavar="SIP_CODE",                           help="Listen on a SIP code 'guavasip-...'.")
    args = parser.parse_args()

    if args.phone is not None:
        agent.listen_phone(args.phone or os.environ["GUAVA_AGENT_NUMBER"])
    elif args.webrtc is not None:
        agent.listen_webrtc(args.webrtc or None)
    elif args.sip:
        agent.listen_sip(args.sip)
    else:
        agent.call_local()
