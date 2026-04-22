import guava
import os
import logging
from guava import logging_utils
import argparse
import datetime

from google.oauth2 import service_account
from googleapiclient.discovery import build


SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = os.environ["SHEETS_SPREADSHEET_ID"]
SHEET_NAME = os.environ.get("SHEETS_SURVEY_TAB", "Survey Responses")

_sheets_service = None


def build_sheets_service():
    creds = service_account.Credentials.from_service_account_file(
        os.environ["GOOGLE_CREDENTIALS_FILE"],
        scopes=SCOPES,
    )
    return build("sheets", "v4", credentials=creds)


def append_response(
    service,
    customer_name: str,
    phone: str,
    rating: str,
    highlight: str,
    improvement: str,
    recommend: str,
) -> None:
    """Appends one survey response row to the sheet."""
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A1",
        valueInputOption="USER_ENTERED",
        body={
            "values": [
                [timestamp, customer_name, phone, rating, highlight, improvement, recommend]
            ]
        },
    ).execute()


agent = guava.Agent(
    name="Casey",
    organization="Apex Solutions",
    purpose=(
        "to collect brief post-service feedback from Apex Solutions customers "
        "so the team can keep improving"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    global _sheets_service
    _sheets_service = build_sheets_service()
    call.reach_person(contact_full_name=call.get_variable("customer_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    customer_name = call.get_variable("customer_name")

    if outcome == "unavailable":
        call.hangup(
            final_instructions=(
                f"Hi, this message is for {customer_name}. This is Casey from Apex Solutions. "
                "We'd love to hear about your recent experience with us. "
                "Please feel free to call us back at your convenience. Thank you!"
            )
        )
    elif outcome == "available":
        call.set_task(
            "save_response",
            objective=(
                f"Call {customer_name} for a quick satisfaction survey about their recent "
                "experience with Apex Solutions. Collect a rating, what went well, and "
                "any improvement suggestions."
            ),
            checklist=[
                guava.Say(
                    f"Hi, may I please speak with {customer_name}? "
                    f"... Hi {customer_name.split()[0]}, this is Casey calling from Apex Solutions. "
                    "We just wanted to reach out with a quick two-minute survey about your recent "
                    "experience — is now an okay time?"
                ),
                guava.Field(
                    key="rating",
                    field_type="multiple_choice",
                    description=(
                        "Ask them to rate their overall experience on a scale of 1 to 5, "
                        "where 1 is very dissatisfied and 5 is very satisfied."
                    ),
                    choices=["1", "2", "3", "4", "5"],
                    required=True,
                ),
                guava.Field(
                    key="highlight",
                    field_type="text",
                    description=(
                        "Ask what they felt went particularly well — or what stood out "
                        "most about their experience. Keep it brief."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="improvement",
                    field_type="text",
                    description=(
                        "Ask if there's anything we could have done better. "
                        "Let them know their feedback goes directly to the team."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="recommend",
                    field_type="multiple_choice",
                    description=(
                        "Ask whether they would recommend Apex Solutions to a colleague or friend."
                    ),
                    choices=["yes", "no", "maybe"],
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("save_response")
def on_done(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    phone = call.get_variable("phone")

    rating = call.get_field("rating") or ""
    highlight = call.get_field("highlight") or ""
    improvement = call.get_field("improvement") or ""
    recommend = call.get_field("recommend") or ""

    logging.info(
        "Saving survey — customer: %s, rating: %s, recommend: %s",
        customer_name, rating, recommend,
    )

    try:
        append_response(
            _sheets_service,
            customer_name,
            phone,
            rating,
            highlight,
            improvement,
            recommend,
        )
        logging.info("Survey response saved for %s", customer_name)
    except Exception as e:
        logging.error("Failed to save survey response: %s", e)

    call.hangup(
        final_instructions=(
            f"Thank {customer_name.split()[0]} sincerely for their time and feedback. "
            "Let them know it goes directly to the Apex Solutions team and they genuinely "
            "appreciate it. Wish them a great day."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(description="Outbound post-service survey call")
    parser.add_argument("to_number", help="Customer's phone number to call (E.164)")
    parser.add_argument("--name", required=True, help="Customer's full name")
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.to_number,
        variables={
            "customer_name": args.name,
            "phone": args.to_number,
        },
    )
