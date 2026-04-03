import guava
import os
import logging
import requests
from datetime import datetime

logging.basicConfig(level=logging.INFO)

SALESFORCE_INSTANCE_URL = os.environ["SALESFORCE_INSTANCE_URL"]
SALESFORCE_ACCESS_TOKEN = os.environ["SALESFORCE_ACCESS_TOKEN"]
SF_HEADERS = {
    "Authorization": f"Bearer {SALESFORCE_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}
API_BASE = f"{SALESFORCE_INSTANCE_URL}/services/data/v66.0"


def find_account_by_name(account_name: str) -> dict | None:
    """Searches for a Salesforce Account by name. Returns the account or None."""
    q = (
        f"SELECT Id, Name, Type, Industry, AnnualRevenue, NumberOfEmployees, "
        f"Phone, BillingCity, BillingState, OwnerId, LastActivityDate "
        f"FROM Account WHERE Name LIKE '%{account_name}%' LIMIT 1"
    )
    resp = requests.get(
        f"{API_BASE}/query",
        headers=SF_HEADERS,
        params={"q": q},
        timeout=10,
    )
    resp.raise_for_status()
    records = resp.json().get("records", [])
    return records[0] if records else None


def get_open_cases_count(account_id: str) -> int:
    """Returns the count of open Cases for a given Account."""
    q = f"SELECT COUNT() FROM Case WHERE AccountId = '{account_id}' AND Status != 'Closed'"
    resp = requests.get(
        f"{API_BASE}/query",
        headers=SF_HEADERS,
        params={"q": q},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("totalSize", 0)


def get_open_opportunities(account_id: str) -> list:
    """Returns open Opportunities for a given Account."""
    q = (
        f"SELECT Name, StageName, Amount, CloseDate FROM Opportunity "
        f"WHERE AccountId = '{account_id}' AND IsClosed = false LIMIT 5"
    )
    resp = requests.get(
        f"{API_BASE}/query",
        headers=SF_HEADERS,
        params={"q": q},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("records", [])


class AccountInquiryController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Pinnacle Group",
            agent_name="Drew",
            agent_purpose=(
                "to help account managers and customers quickly look up Salesforce account "
                "details, open cases, and active opportunities"
            ),
        )

        self.set_task(
            objective=(
                "A caller wants to look up details on a Salesforce account. Collect the account "
                "name, retrieve the account record, and share a clear summary of their status, "
                "open cases, and active opportunities."
            ),
            checklist=[
                guava.Say(
                    "Thanks for calling Pinnacle Group. I'm Drew, and I can help you look up "
                    "account details. Just let me know which account you'd like information on."
                ),
                guava.Field(
                    key="account_name",
                    field_type="text",
                    description="Ask the caller for the name of the account they want to look up.",
                    required=True,
                ),
                guava.Field(
                    key="info_needed",
                    field_type="multiple_choice",
                    description="Ask what type of information they need.",
                    choices=["account overview", "open cases", "active opportunities", "all of the above"],
                    required=True,
                ),
            ],
            on_complete=self.fetch_and_summarize,
        )

        self.accept_call()

    def fetch_and_summarize(self):
        account_name = self.get_field("account_name") or ""
        info_needed = self.get_field("info_needed") or "all of the above"

        logging.info("Looking up Salesforce Account: %s", account_name)
        try:
            account = find_account_by_name(account_name)
        except Exception as e:
            logging.error("Account lookup failed: %s", e)
            account = None

        if not account:
            self.hangup(
                final_instructions=(
                    f"Let the caller know you couldn't find an account matching '{account_name}'. "
                    "Suggest they check the exact name or narrow down the search. Be helpful."
                )
            )
            return

        account_id = account["Id"]
        name = account.get("Name", account_name)
        acct_type = account.get("Type") or "N/A"
        industry = account.get("Industry") or "N/A"
        last_activity = account.get("LastActivityDate") or "none recorded"
        billing_city = account.get("BillingCity") or ""
        billing_state = account.get("BillingState") or ""
        location = f"{billing_city}, {billing_state}".strip(", ") or "N/A"

        summary_parts = [f"Account: {name}"]

        if info_needed in ("account overview", "all of the above"):
            summary_parts += [
                f"Type: {acct_type}",
                f"Industry: {industry}",
                f"Location: {location}",
                f"Last activity: {last_activity}",
            ]

        if info_needed in ("open cases", "all of the above"):
            try:
                open_cases = get_open_cases_count(account_id)
                summary_parts.append(f"Open support cases: {open_cases}")
            except Exception as e:
                logging.error("Failed to fetch cases for %s: %s", account_id, e)

        if info_needed in ("active opportunities", "all of the above"):
            try:
                opps = get_open_opportunities(account_id)
                if opps:
                    opp_lines = []
                    for o in opps:
                        amount = f"${o['Amount']:,.0f}" if o.get("Amount") else "no amount"
                        opp_lines.append(f"{o['Name']} ({o.get('StageName', 'unknown stage')}, {amount})")
                    summary_parts.append("Active opportunities: " + "; ".join(opp_lines))
                else:
                    summary_parts.append("Active opportunities: none")
            except Exception as e:
                logging.error("Failed to fetch opportunities for %s: %s", account_id, e)

        logging.info("Account summary for %s: %s", account_id, summary_parts)

        self.hangup(
            final_instructions=(
                "Share the following account summary with the caller in a clear, conversational way. "
                "Read each piece of information naturally — don't just list it robotically. "
                f"Summary: {'; '.join(summary_parts)}. "
                "Thank them for calling Pinnacle Group."
            )
        )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=AccountInquiryController,
    )
