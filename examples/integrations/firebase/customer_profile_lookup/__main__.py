import logging
import os

import firebase_admin
import guava
from firebase_admin import credentials, firestore
from guava import logging_utils

cred = credentials.Certificate(os.environ["GOOGLE_APPLICATION_CREDENTIALS"])
firebase_admin.initialize_app(cred)
db = firestore.client()

CUSTOMERS_COLLECTION = os.environ.get("FIRESTORE_CUSTOMERS_COLLECTION", "customers")


def lookup_customer_by_email(email: str) -> dict | None:
    """Return the first customer document matching the given email."""
    docs = (
        db.collection(CUSTOMERS_COLLECTION)
        .where("email", "==", email.lower().strip())
        .limit(1)
        .stream()
    )
    for doc in docs:
        data = doc.to_dict()
        data["_id"] = doc.id
        return data
    return None


def lookup_customer_by_phone(phone: str) -> dict | None:
    """Return the first customer document matching the given phone number."""
    normalized = "".join(c for c in phone if c.isdigit())
    docs = (
        db.collection(CUSTOMERS_COLLECTION)
        .where("phone_normalized", "==", normalized)
        .limit(1)
        .stream()
    )
    for doc in docs:
        data = doc.to_dict()
        data["_id"] = doc.id
        return data
    return None


def update_last_contact(customer_id: str) -> None:
    db.collection(CUSTOMERS_COLLECTION).document(customer_id).update(
        {"last_contact": firestore.SERVER_TIMESTAMP}
    )


agent = guava.Agent(
    name="Casey",
    organization="Crestline Services",
    purpose=(
        "to assist Crestline Services customers by looking up their account "
        "and helping with their inquiry"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "look_up_and_assist",
        objective=(
            "A customer has called. Verify their identity by looking up their account "
            "in Firestore, then personalize the conversation based on their profile."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Crestline Services. This is Casey. "
                "Let me pull up your account."
            ),
            guava.Field(
                key="lookup_method",
                field_type="multiple_choice",
                description=(
                    "Ask whether they'd like to verify with their email address or "
                    "the phone number on their account."
                ),
                choices=["email address", "phone number on account"],
                required=True,
            ),
            guava.Field(
                key="lookup_value",
                field_type="text",
                description=(
                    "Ask for the value they chose — either their email address or "
                    "their phone number."
                ),
                required=True,
            ),
            guava.Field(
                key="inquiry_reason",
                field_type="text",
                description=(
                    "Ask what they're calling about today. "
                    "Capture a brief description of their need."
                ),
                required=True,
            ),
        ],
    )


@agent.on_task_complete("look_up_and_assist")
def on_done(call: guava.Call) -> None:
    method = call.get_field("lookup_method") or "email address"
    value = (call.get_field("lookup_value") or "").strip()
    inquiry = call.get_field("inquiry_reason") or ""

    logging.info("Looking up customer by %s: %s", method, value)

    try:
        if "email" in method:
            customer = lookup_customer_by_email(value)
        else:
            customer = lookup_customer_by_phone(value)
    except Exception as e:
        logging.error("Firestore lookup failed: %s", e)
        customer = None

    if not customer:
        call.hangup(
            final_instructions=(
                "Let the caller know you weren't able to find an account matching "
                "their information. Apologize for the inconvenience and offer to "
                "transfer them to a team member who can help verify their account manually. "
                "Thank them for their patience."
            )
        )
        return

    customer_id = customer.get("_id", "")
    name = customer.get("name") or customer.get("first_name") or "there"
    tier = customer.get("tier") or customer.get("plan") or ""
    notes = customer.get("notes") or ""

    tier_note = f" They are on the {tier} tier." if tier else ""
    notes_note = f" Account notes: {notes}." if notes else ""

    logging.info("Found customer %s (ID: %s)", name, customer_id)

    try:
        if customer_id:
            update_last_contact(customer_id)
    except Exception as e:
        logging.warning("Could not update last_contact for %s: %s", customer_id, e)

    call.hangup(
        final_instructions=(
            f"Greet {name} by name — you've successfully verified their account.{tier_note}{notes_note} "
            f"Now address their inquiry: '{inquiry}'. "
            "Be warm and personalized — you know who they are. "
            "If their inquiry requires further action (e.g. a callback, ticket, or transfer), "
            "let them know the next steps. Thank them for being a Crestline customer."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
