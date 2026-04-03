import guava
import os
import logging
import requests

logging.basicConfig(level=logging.INFO)

BASE_URL = "https://sandbox.plaid.com"


def get_headers() -> dict:
    return {
        "Content-Type": "application/json",
        "PLAID-CLIENT-ID": os.environ["PLAID_CLIENT_ID"],
        "PLAID-SECRET": os.environ["PLAID_SECRET"],
    }


def lookup_access_token(user_id: str) -> str | None:
    """Placeholder: retrieve the Plaid access_token for this user from your database."""
    raise NotImplementedError("Replace with a real DB lookup for the user's Plaid access_token.")


def get_income_summary(access_token: str) -> dict | None:
    """Fetches payroll income data via /credit/payroll_income/get."""
    payload = {"access_token": access_token}
    resp = requests.post(
        f"{BASE_URL}/credit/payroll_income/get",
        headers=get_headers(),
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    items = data.get("items", [])
    if not items:
        return None

    payroll_income = items[0].get("payroll_income", [])
    if not payroll_income:
        return None

    latest = payroll_income[0]
    pay_stubs = latest.get("pay_stubs", [])
    if not pay_stubs:
        return None

    stub = pay_stubs[0]
    employer = stub.get("employer", {}).get("name", "Unknown employer")
    net_pay = stub.get("net_pay", {})
    gross_pay = stub.get("gross_earnings", {})
    pay_period = stub.get("pay_period_details", {})

    return {
        "employer": employer,
        "net_pay": net_pay.get("current_amount", 0),
        "gross_pay": gross_pay.get("current_amount", 0),
        "currency": net_pay.get("iso_currency_code", "USD"),
        "pay_frequency": pay_period.get("pay_frequency", "unknown"),
        "period_start": pay_period.get("start_date", ""),
        "period_end": pay_period.get("end_date", ""),
    }


class IncomeVerificationController(guava.CallController):
    def __init__(self, user_id: str):
        super().__init__()

        self._user_id = user_id
        self._income: dict | None = None

        try:
            access_token = lookup_access_token(user_id)
            if access_token:
                self._income = get_income_summary(access_token)
                logging.info("Loaded income data for user %s: %s", user_id, self._income)
        except Exception as e:
            logging.error("Failed to load income data: %s", e)

        income = self._income
        if income:
            context = (
                f"Employer: {income['employer']}. "
                f"Most recent net pay: ${income['net_pay']:.2f} {income['currency']}. "
                f"Gross pay: ${income['gross_pay']:.2f}. "
                f"Pay frequency: {income['pay_frequency']}. "
                f"Pay period: {income['period_start']} to {income['period_end']}."
            )
        else:
            context = "Income data could not be loaded from connected accounts."

        self.set_persona(
            organization_name="ClearPath Banking",
            agent_name="Jordan",
            agent_purpose=(
                "to help ClearPath Banking customers verify their income details on file "
                "as part of a loan or credit application"
            ),
        )

        self.set_task(
            objective=(
                "A customer has called to verify the income information on their loan application. "
                f"The following income data was retrieved from their connected payroll account: {context} "
                "Confirm the details with the customer and ask if anything needs to be corrected."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling ClearPath Banking. This is Jordan. "
                    "I'm calling about the income information we have on file for your application."
                ),
                guava.Field(
                    key="details_correct",
                    field_type="multiple_choice",
                    description=(
                        "Read back the employer name, pay frequency, and most recent net pay. "
                        "Ask if this information is correct."
                    ),
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="correction_note",
                    field_type="text",
                    description=(
                        "If the customer says no, ask them to describe what is incorrect "
                        "so you can flag it for the loan officer."
                    ),
                    required=False,
                ),
            ],
            on_complete=self.handle_verification,
        )

        self.accept_call()

    def handle_verification(self):
        details_correct = self.get_field("details_correct") or "yes"
        correction_note = self.get_field("correction_note") or ""

        logging.info(
            "Income verification for user %s: correct=%s, note=%s",
            self._user_id,
            details_correct,
            correction_note,
        )

        if details_correct == "yes":
            self.hangup(
                final_instructions=(
                    "Let the customer know their income information has been confirmed and their application "
                    "will continue processing. They can expect to hear back within 2-3 business days. "
                    "Thank them for calling ClearPath Banking."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Let the customer know you've noted the correction: '{correction_note}'. "
                    "A loan officer will review the updated information and may reach out if further "
                    "documentation is needed. Thank them for calling ClearPath Banking."
                )
            )
