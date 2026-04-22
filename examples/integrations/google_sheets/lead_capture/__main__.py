import datetime
import logging
import os

import guava
from google.oauth2 import service_account
from googleapiclient.discovery import build
from guava import logging_utils

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = os.environ["SHEETS_SPREADSHEET_ID"]

_sheets_service = None
SHEET_NAME = os.environ.get("SHEETS_LEAD_TAB", "Leads")


def build_sheets_service():
    creds = service_account.Credentials.from_service_account_file(
        os.environ["GOOGLE_CREDENTIALS_FILE"],
        scopes=SCOPES,
    )
    return build("sheets", "v4", credentials=creds)


def append_lead(
    service,
    name: str,
    email: str,
    phone: str,
    interest: str,
) -> None:
    """Appends one row to the Leads sheet."""
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A1",
        valueInputOption="USER_ENTERED",
        body={"values": [[timestamp, name, email, phone, interest, "new"]]},
    ).execute()


agent = guava.Agent(
    name="Jordan",
    organization="Apex Solutions",
    purpose=(
        "to capture contact information from callers who are interested in "
        "Apex Solutions products and services"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    global _sheets_service
    _sheets_service = build_sheets_service()

    call.set_task(
        "log_lead",
        objective=(
            "A caller has expressed interest in Apex Solutions. "
            "Collect their name, email, phone, and area of interest, "
            "then log them as a new lead."
        ),
        checklist=[
            guava.Say(
                "Thanks for calling Apex Solutions. I'm Jordan. "
                "I'd love to make sure one of our team members follows up with you. "
                "Mind if I grab a few details?"
            ),
            guava.Field(
                key="name",
                field_type="text",
                description="Ask for the caller's full name.",
                required=True,
            ),
            guava.Field(
                key="email",
                field_type="text",
                description="Ask for the best email address to reach them.",
                required=True,
            ),
            guava.Field(
                key="phone",
                field_type="text",
                description=(
                    "Ask for a callback phone number in case we get disconnected. "
                    "Capture digits only."
                ),
                required=False,
            ),
            guava.Field(
                key="interest",
                field_type="multiple_choice",
                description="Ask which area they're most interested in.",
                choices=[
                    "enterprise software",
                    "professional services",
                    "support & maintenance",
                    "training & onboarding",
                    "general inquiry",
                ],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("log_lead")
def on_done(call: guava.Call) -> None:
    name = call.get_field("name") or ""
    email = call.get_field("email") or ""
    phone = call.get_field("phone") or ""
    interest = call.get_field("interest") or ""

    logging.info("Logging lead — name: %s, interest: %s", name, interest)

    try:
        append_lead(_sheets_service, name, email, phone, interest)
        logging.info("Lead appended to sheet for %s", name)
    except Exception as e:
        logging.error("Failed to append lead: %s", e)
        call.hangup(
            final_instructions=(
                f"Apologize to {name} — there was a technical issue saving their info. "
                "Let them know someone from Apex Solutions will still follow up and "
                "to try calling again if they don't hear back. Thank them."
            )
        )
        return

    call.hangup(
        final_instructions=(
            f"Let {name} know their information has been captured and a team member "
            "will follow up within one business day. "
            "Thank them for their interest in Apex Solutions."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
