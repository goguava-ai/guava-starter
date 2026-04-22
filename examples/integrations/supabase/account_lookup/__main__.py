import guava
import os
import logging
from guava import logging_utils
import requests


SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
REST_URL = f"{SUPABASE_URL}/rest/v1"


def get_headers() -> dict:
    service_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def find_account_by_email(email: str) -> dict | None:
    resp = requests.get(
        f"{REST_URL}/users",
        headers=get_headers(),
        params={"email": f"eq.{email}", "limit": 1},
        timeout=10,
    )
    resp.raise_for_status()
    rows = resp.json()
    return rows[0] if rows else None


def find_account_by_phone(phone: str) -> dict | None:
    resp = requests.get(
        f"{REST_URL}/users",
        headers=get_headers(),
        params={"phone": f"eq.{phone}", "limit": 1},
        timeout=10,
    )
    resp.raise_for_status()
    rows = resp.json()
    return rows[0] if rows else None


class AccountLookupController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Clearline",
            agent_name="Jamie",
            agent_purpose="to help Clearline customers look up their account information by phone",
        )

        self.set_task(
            objective=(
                "A customer has called to look up their account. "
                "Verify their identity using email or phone number, then read back their account status and details."
            ),
            checklist=[
                guava.Say(
                    "Welcome to Clearline support. This is Jamie. I can help you look up your account."
                ),
                guava.Field(
                    key="lookup_method",
                    field_type="multiple_choice",
                    description="Ask how they'd like to verify their identity.",
                    choices=["email", "phone number"],
                    required=True,
                ),
                guava.Field(
                    key="email",
                    field_type="text",
                    description="If by email, ask for their email address.",
                    required=False,
                ),
                guava.Field(
                    key="phone",
                    field_type="text",
                    description="If by phone, ask for the phone number on the account.",
                    required=False,
                ),
            ],
            on_complete=self.lookup_account,
        )

        self.accept_call()

    def lookup_account(self):
        lookup_method = self.get_field("lookup_method") or "email"
        email = self.get_field("email") or ""
        phone = self.get_field("phone") or ""

        logging.info("Looking up account by %s", lookup_method)

        account = None
        try:
            if lookup_method == "email" and email:
                account = find_account_by_email(email)
            elif phone:
                account = find_account_by_phone(phone)
            logging.info("Account found: %s", account.get("id") if account else None)
        except Exception as e:
            logging.error("Failed to look up account: %s", e)

        if not account:
            self.hangup(
                final_instructions=(
                    "Let the customer know we couldn't find an account matching that information. "
                    "Ask them to double-check their email or phone number and call back. "
                    "Thank them for calling Clearline."
                )
            )
            return

        account_id = account.get("id", "")
        name = account.get("full_name") or account.get("name") or "on file"
        plan = account.get("plan") or account.get("subscription_plan") or ""
        status = account.get("status") or account.get("account_status") or "active"
        created = account.get("created_at", "")[:10] if account.get("created_at") else ""

        details = f"Account found for {name}."
        details += f" Status: {status}."
        if plan:
            details += f" Plan: {plan}."
        if created:
            details += f" Member since: {created}."

        self.hangup(
            final_instructions=(
                f"Read the following account details to the customer: {details} "
                "Thank them for calling Clearline."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=AccountLookupController,
    )
