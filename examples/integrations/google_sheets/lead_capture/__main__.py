import guava
import os
import logging
import datetime

from google.oauth2 import service_account
from googleapiclient.discovery import build

logging.basicConfig(level=logging.INFO)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = os.environ["SHEETS_SPREADSHEET_ID"]
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


class LeadCaptureController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.service = build_sheets_service()

        self.set_persona(
            organization_name="Apex Solutions",
            agent_name="Jordan",
            agent_purpose=(
                "to capture contact information from callers who are interested in "
                "Apex Solutions products and services"
            ),
        )

        self.set_task(
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
            on_complete=self.log_lead,
        )

        self.accept_call()

    def log_lead(self):
        name = self.get_field("name") or ""
        email = self.get_field("email") or ""
        phone = self.get_field("phone") or ""
        interest = self.get_field("interest") or ""

        logging.info("Logging lead — name: %s, interest: %s", name, interest)

        try:
            append_lead(self.service, name, email, phone, interest)
            logging.info("Lead appended to sheet for %s", name)
        except Exception as e:
            logging.error("Failed to append lead: %s", e)
            self.hangup(
                final_instructions=(
                    f"Apologize to {name} — there was a technical issue saving their info. "
                    "Let them know someone from Apex Solutions will still follow up and "
                    "to try calling again if they don't hear back. Thank them."
                )
            )
            return

        self.hangup(
            final_instructions=(
                f"Let {name} know their information has been captured and a team member "
                "will follow up within one business day. "
                "Thank them for their interest in Apex Solutions."
            )
        )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=LeadCaptureController,
    )
