import guava
import os
import logging
import requests
from datetime import datetime

logging.basicConfig(level=logging.INFO)

ACCESS_TOKEN = os.environ["DYNAMICS_ACCESS_TOKEN"]
ORG_URL = os.environ["DYNAMICS_ORG_URL"]  # e.g. https://yourorg.crm.dynamics.com

_BASE_HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json",
    "OData-MaxVersion": "4.0",
    "OData-Version": "4.0",
    "Accept": "application/json",
}
HEADERS = {**_BASE_HEADERS, "Prefer": "return=representation"}  # for POST/PATCH that return data
GET_HEADERS = _BASE_HEADERS  # for GET requests

API_BASE = f"{ORG_URL}/api/data/v9.2"

STATUS_LABELS = {
    1: "In Progress",
    2: "On Hold",
    3: "Waiting for Details",
    4: "Researching",
    5: "Resolved",
    6: "Cancelled",
}

PRIORITY_LABELS = {
    1: "High",
    2: "Normal",
    3: "Low",
}


def find_contact_by_email(email: str) -> dict | None:
    """Searches Dynamics 365 for a contact by email address. Returns the contact object or None."""
    resp = requests.get(
        f"{API_BASE}/contacts",
        headers=GET_HEADERS,
        params={
            "$filter": f"emailaddress1 eq '{email}'",
            "$select": "contactid,fullname,emailaddress1,telephone1,accountid",
        },
        timeout=10,
    )
    resp.raise_for_status()
    results = resp.json().get("value", [])
    return results[0] if results else None


def find_case_by_ticket_number(ticket_number: str) -> dict | None:
    """Looks up a case by its human-readable ticket number. Returns the incident or None."""
    resp = requests.get(
        f"{API_BASE}/incidents",
        headers=GET_HEADERS,
        params={
            "$filter": f"ticketnumber eq '{ticket_number}'",
            "$select": "incidentid,title,statuscode,prioritycode,ticketnumber,createdon,description",
        },
        timeout=10,
    )
    resp.raise_for_status()
    results = resp.json().get("value", [])
    return results[0] if results else None


def get_cases_by_contact(contact_id: str) -> list[dict]:
    """Returns the most recent cases linked to a contact."""
    resp = requests.get(
        f"{API_BASE}/incidents",
        headers=GET_HEADERS,
        params={
            "$filter": f"_customerid_value eq '{contact_id}'",
            "$select": "incidentid,title,statuscode,prioritycode,ticketnumber,createdon,description",
            "$orderby": "createdon desc",
            "$top": "3",
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("value", [])


class CaseStatusCheckController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Pinnacle Solutions",
            agent_name="Sam",
            agent_purpose="to help customers check the status of their support cases with Pinnacle Solutions",
        )

        self.set_task(
            objective=(
                "A customer has called to check on a support case. Ask how they would like to "
                "look up their case — by case number or by email — then collect the relevant value."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Pinnacle Solutions support. My name is Sam. "
                    "I can help you check the status of a support case."
                ),
                guava.Field(
                    key="lookup_method",
                    field_type="multiple_choice",
                    description=(
                        "Ask whether they would like to look up their case by case number "
                        "or by the email address on their account."
                    ),
                    choices=["case-number", "email"],
                    required=True,
                ),
                guava.Field(
                    key="lookup_value",
                    field_type="text",
                    description=(
                        "Ask for the case number if they chose case-number (e.g. CAS-12345-ABCDEF), "
                        "or for their email address if they chose email."
                    ),
                    required=True,
                ),
            ],
            on_complete=self.lookup_case,
        )

        self.accept_call()

    def lookup_case(self):
        method = self.get_field("lookup_method") or "case-number"
        value = (self.get_field("lookup_value") or "").strip()

        logging.info("Case status lookup — method: %s, value: %s", method, value)

        try:
            if method == "case-number":
                case = find_case_by_ticket_number(value)
                if not case:
                    self.hangup(
                        final_instructions=(
                            f"Let the caller know we could not find a case with number {value}. "
                            "Suggest they double-check the number or try looking up by their "
                            "email address instead. Thank them for calling Pinnacle Solutions."
                        )
                    )
                    return
                self._report_case_status(case)

            else:
                # email lookup: find contact first, then their most recent cases
                contact = find_contact_by_email(value)
                if not contact:
                    self.hangup(
                        final_instructions=(
                            "Let the caller know we could not find an account matching that email "
                            "address. Suggest they double-check the address or try looking up by "
                            "case number instead. Thank them for calling Pinnacle Solutions."
                        )
                    )
                    return

                contact_id = contact["contactid"]
                cases = get_cases_by_contact(contact_id)

                if not cases:
                    self.hangup(
                        final_instructions=(
                            "Let the caller know there are no support cases linked to that email "
                            "address. If they need to open a new case they are welcome to call "
                            "back. Thank them for calling Pinnacle Solutions."
                        )
                    )
                    return

                # Report the most recent case; mention if there are others
                case = cases[0]
                extra = len(cases) - 1
                self._report_case_status(case, additional_count=extra)

        except Exception as e:
            logging.error("Case lookup failed: %s", e)
            self.hangup(
                final_instructions=(
                    "Apologize for a technical issue and let the caller know they can also check "
                    "their case status through the Pinnacle Solutions customer portal or by "
                    "replying to their case confirmation email. Thank them for their patience."
                )
            )

    def _report_case_status(self, case: dict, additional_count: int = 0):
        ticket_number = case.get("ticketnumber", "unknown")
        title = case.get("title", "your support request")
        statuscode = case.get("statuscode", 1)
        prioritycode = case.get("prioritycode", 2)
        createdon = case.get("createdon", "")

        status_label = STATUS_LABELS.get(statuscode, f"status {statuscode}")
        priority_label = PRIORITY_LABELS.get(prioritycode, "Normal")

        # Format the creation date for the caller
        created_display = ""
        if createdon:
            try:
                dt = datetime.fromisoformat(createdon.replace("Z", "+00:00"))
                created_display = dt.strftime("%B %d, %Y")
            except ValueError:
                created_display = createdon

        logging.info(
            "Reporting status for case %s — status: %s, priority: %s",
            ticket_number, status_label, priority_label,
        )

        additional_note = ""
        if additional_count > 0:
            additional_note = (
                f" There {'is' if additional_count == 1 else 'are'} also "
                f"{additional_count} other case{'s' if additional_count > 1 else ''} on their account — "
                "let them know they can call back to check those as well."
            )

        self.hangup(
            final_instructions=(
                f"Tell the caller that case {ticket_number} — '{title}' — is currently "
                f"{status_label} with a priority of {priority_label}."
                + (f" The case was opened on {created_display}." if created_display else "")
                + (
                    " Let them know our team is actively working on it and will reach out by email."
                    if statuscode in (1, 4)
                    else (
                        " Let them know the case is on hold and our team will follow up shortly."
                        if statuscode == 2
                        else (
                            " Let them know we are waiting for additional details from them and ask "
                            "them to reply to the case email with any requested information."
                            if statuscode == 3
                            else (
                                " Let them know the case has been resolved and they can open a new "
                                "case if the issue recurs."
                                if statuscode == 5
                                else " Let them know the case has been cancelled."
                            )
                        )
                    )
                )
                + additional_note
                + " Thank them for calling Pinnacle Solutions."
            )
        )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=CaseStatusCheckController,
    )
