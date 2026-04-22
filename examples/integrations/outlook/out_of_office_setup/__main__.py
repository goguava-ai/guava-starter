import guava
import os
import logging
from guava import logging_utils
import requests


GRAPH_ACCESS_TOKEN = os.environ["GRAPH_ACCESS_TOKEN"]
BASE_URL = "https://graph.microsoft.com/v1.0"
HEADERS = {
    "Authorization": f"Bearer {GRAPH_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}
TIMEZONE = os.environ.get("GRAPH_TIMEZONE", "Eastern Standard Time")

DEFAULT_INTERNAL_TEMPLATE = (
    "Hi, I'm currently out of the office and will return on {return_date}. "
    "For urgent matters, please contact {backup_contact}. "
    "I'll respond to your email when I return."
)
DEFAULT_EXTERNAL_TEMPLATE = (
    "Thank you for your email. I'm currently out of the office and will return on {return_date}. "
    "I'll respond to your message when I'm back. "
    "For urgent inquiries, please contact {backup_contact}."
)


def set_automatic_replies(
    start_date: str,
    end_date: str,
    internal_message: str,
    external_message: str,
) -> None:
    """Enables scheduled automatic replies via PATCH /me/mailboxSettings."""
    payload = {
        "automaticRepliesSetting": {
            "status": "scheduled",
            "scheduledStartDateTime": {
                "dateTime": f"{start_date}T00:00:00",
                "timeZone": TIMEZONE,
            },
            "scheduledEndDateTime": {
                "dateTime": f"{end_date}T23:59:00",
                "timeZone": TIMEZONE,
            },
            "internalReplyMessage": internal_message,
            "externalReplyMessage": external_message,
        }
    }
    resp = requests.patch(
        f"{BASE_URL}/me/mailboxSettings",
        headers=HEADERS,
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()


def disable_automatic_replies() -> None:
    """Turns off automatic replies."""
    payload = {"automaticRepliesSetting": {"status": "disabled"}}
    resp = requests.patch(
        f"{BASE_URL}/me/mailboxSettings",
        headers=HEADERS,
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()


agent = guava.Agent(
    name="Jordan",
    organization="Meridian Partners",
    purpose=(
        "to help Meridian Partners employees set up or disable their Outlook "
        "out-of-office automatic reply over the phone"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "configure_ooo",
        objective=(
            "A team member has called to configure their Outlook out-of-office auto-reply. "
            "Collect the dates, backup contact, and any custom message, then activate it."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Meridian Partners IT support. I'm Jordan. "
                "I can set up your Outlook out-of-office reply right now."
            ),
            guava.Field(
                key="action",
                field_type="multiple_choice",
                description=(
                    "Ask whether they want to set up a new out-of-office reply "
                    "or turn off an existing one."
                ),
                choices=["set up out-of-office", "turn off out-of-office"],
                required=True,
            ),
            guava.Field(
                key="start_date",
                field_type="date",
                description=(
                    "If setting up, ask for the first day they'll be out of office. "
                    "Skip if turning off."
                ),
                required=False,
            ),
            guava.Field(
                key="end_date",
                field_type="date",
                description="Ask for their last day out.",
                required=False,
            ),
            guava.Field(
                key="backup_contact",
                field_type="text",
                description=(
                    "Ask who should be contacted for urgent matters while they're away. "
                    "Capture their name or email address."
                ),
                required=False,
            ),
            guava.Field(
                key="custom_message",
                field_type="text",
                description=(
                    "Ask if they'd like a custom message, or if the standard Meridian Partners "
                    "template is fine. Capture their custom message if they have one."
                ),
                required=False,
            ),
        ],
    )


@agent.on_task_complete("configure_ooo")
def on_done(call: guava.Call) -> None:
    action = call.get_field("action") or "set up out-of-office"
    start_date = call.get_field("start_date") or ""
    end_date = call.get_field("end_date") or ""
    backup_contact = call.get_field("backup_contact") or "your manager"
    custom_message = call.get_field("custom_message") or ""

    if "turn off" in action:
        logging.info("Disabling automatic replies")
        try:
            disable_automatic_replies()
            call.hangup(
                final_instructions=(
                    "Let the caller know their out-of-office auto-reply has been turned off. "
                    "All incoming emails will now go to their inbox normally. "
                    "Thank them for calling Meridian Partners."
                )
            )
        except Exception as e:
            logging.error("Failed to disable automatic replies: %s", e)
            call.hangup(
                final_instructions=(
                    "Apologize — there was an issue turning off the auto-reply. "
                    "Ask them to disable it directly in Outlook settings. Thank them."
                )
            )
        return

    if not start_date or not end_date:
        call.hangup(
            final_instructions=(
                "Let the caller know we need both a start and end date to set up the auto-reply. "
                "Ask them to call back with both dates. Thank them for calling."
            )
        )
        return

    # Build the messages — use custom if provided, otherwise fill the template
    if custom_message:
        internal_message = custom_message
        external_message = custom_message
    else:
        internal_message = DEFAULT_INTERNAL_TEMPLATE.format(
            return_date=end_date, backup_contact=backup_contact
        )
        external_message = DEFAULT_EXTERNAL_TEMPLATE.format(
            return_date=end_date, backup_contact=backup_contact
        )

    logging.info(
        "Setting OOO from %s to %s, backup: %s", start_date, end_date, backup_contact
    )

    try:
        set_automatic_replies(start_date, end_date, internal_message, external_message)
    except Exception as e:
        logging.error("Failed to set automatic replies: %s", e)
        call.hangup(
            final_instructions=(
                "Apologize — there was a technical issue setting up the auto-reply. "
                "Ask them to configure it directly in Outlook or call back. Thank them."
            )
        )
        return

    call.hangup(
        final_instructions=(
            f"Let the caller know their out-of-office auto-reply has been set up successfully. "
            f"It will be active from {start_date} through {end_date}. "
            f"Anyone who emails them will be told to contact {backup_contact} for urgent matters. "
            "Wish them a great time away and thank them for calling Meridian Partners."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
