import guava
import os
import logging
from guava import logging_utils
import json
import requests
from requests_oauthlib import OAuth1
from datetime import datetime, timezone


NS_ACCOUNT_ID = os.environ["NETSUITE_ACCOUNT_ID"]   # e.g. 1234567
NS_CONSUMER_KEY = os.environ["NETSUITE_CONSUMER_KEY"]
NS_CONSUMER_SECRET = os.environ["NETSUITE_CONSUMER_SECRET"]
NS_TOKEN_KEY = os.environ["NETSUITE_TOKEN_KEY"]
NS_TOKEN_SECRET = os.environ["NETSUITE_TOKEN_SECRET"]

# NetSuite REST Record API base — account ID is lowercased with dashes replacing underscores
_acct = NS_ACCOUNT_ID.lower().replace("_", "-")
REST_BASE = f"https://{_acct}.suitetalk.api.netsuite.com/services/rest/record/v1"


def _auth() -> OAuth1:
    return OAuth1(
        NS_CONSUMER_KEY,
        NS_CONSUMER_SECRET,
        NS_TOKEN_KEY,
        NS_TOKEN_SECRET,
        signature_method="HMAC-SHA256",
        realm=NS_ACCOUNT_ID,
    )


def find_invoices_by_email(email: str) -> list:
    """Searches for invoices linked to a customer with the given email."""
    resp = requests.get(
        f"{REST_BASE}/invoice",
        auth=_auth(),
        params={"q": f"email IS {email}", "limit": 5},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("items", [])


def get_invoice(invoice_id: str) -> dict | None:
    resp = requests.get(
        f"{REST_BASE}/invoice/{invoice_id}",
        auth=_auth(),
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def find_invoice_by_number(invoice_number: str) -> dict | None:
    """Searches for an invoice by tranid (transaction number)."""
    resp = requests.get(
        f"{REST_BASE}/invoice",
        auth=_auth(),
        params={"q": f"tranid IS {invoice_number}", "limit": 1},
        timeout=10,
    )
    resp.raise_for_status()
    items = resp.json().get("items", [])
    if not items:
        return None
    return get_invoice(items[0]["id"])


def format_invoice(inv: dict) -> str:
    tran_id = inv.get("tranid", "")
    amount = inv.get("amountremaining", inv.get("total", ""))
    currency = inv.get("currency", {}).get("refName", "USD") if isinstance(inv.get("currency"), dict) else "USD"
    due_date = inv.get("duedate", "")
    status = inv.get("status", {}).get("refName", "") if isinstance(inv.get("status"), dict) else inv.get("status", "")
    return f"Invoice {tran_id}: {status}, ${amount} {currency} due {due_date}"


class InvoiceInquiryController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Meridian Solutions",
            agent_name="Sam",
            agent_purpose=(
                "to help customers look up and inquire about invoices in our NetSuite system"
            ),
        )

        self.set_task(
            objective=(
                "A customer is calling about an invoice. Collect their invoice number or "
                "email and look up the details in NetSuite."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Meridian Solutions accounts receivable. I'm Sam. "
                    "I can look up your invoice information right now."
                ),
                guava.Field(
                    key="lookup_type",
                    field_type="multiple_choice",
                    description="Ask whether they have a specific invoice number or just their email.",
                    choices=["invoice number", "email address"],
                    required=True,
                ),
                guava.Field(
                    key="identifier",
                    field_type="text",
                    description="Ask them to provide their invoice number or email address.",
                    required=True,
                ),
                guava.Field(
                    key="inquiry_type",
                    field_type="multiple_choice",
                    description="Ask what their question is about.",
                    choices=[
                        "balance due",
                        "payment status",
                        "dispute or discrepancy",
                        "need a copy",
                        "other",
                    ],
                    required=True,
                ),
            ],
            on_complete=self.look_up_invoice,
        )

        self.accept_call()

    def look_up_invoice(self):
        lookup_type = self.get_field("lookup_type")
        identifier = (self.get_field("identifier") or "").strip()
        inquiry_type = self.get_field("inquiry_type")
        by_invoice = lookup_type == "invoice number"

        logging.info(
            "NetSuite invoice inquiry — type: %s, id: %s, question: %s",
            lookup_type, identifier, inquiry_type,
        )

        try:
            if by_invoice:
                invoice = find_invoice_by_number(identifier)
                invoices = [invoice] if invoice else []
            else:
                invoices = find_invoices_by_email(identifier)

            result = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "agent": "Sam",
                "use_case": "invoice_inquiry",
                "lookup_type": lookup_type,
                "identifier": identifier,
                "inquiry_type": inquiry_type,
                "invoices_found": len(invoices),
            }
            print(json.dumps(result, indent=2))

            if not invoices:
                self.hangup(
                    final_instructions=(
                        f"Let the caller know we couldn't find any invoices for "
                        f"{'invoice number' if by_invoice else 'email'} {identifier}. "
                        "Ask them to verify the information and call back, or offer to transfer "
                        "them to an accounts receivable specialist. Thank them for calling."
                    )
                )
                return

            inv = invoices[0]
            summary = format_invoice(inv)
            tran_id = inv.get("tranid", identifier)
            balance = inv.get("amountremaining", "")
            currency = inv.get("currency", {}).get("refName", "USD") if isinstance(inv.get("currency"), dict) else "USD"
            due_date = inv.get("duedate", "")
            status = inv.get("status", {}).get("refName", "") if isinstance(inv.get("status"), dict) else inv.get("status", "")

            if inquiry_type == "balance due":
                self.hangup(
                    final_instructions=(
                        f"Let the caller know that invoice {tran_id} has a remaining balance "
                        f"of ${balance} {currency}, due on {due_date}. "
                        "If they'd like to pay by phone, offer to transfer them to our payment "
                        "processing line. Thank them for calling Meridian Solutions."
                    )
                )
            elif inquiry_type == "payment status":
                self.hangup(
                    final_instructions=(
                        f"Let the caller know that invoice {tran_id} is currently in '{status}' "
                        f"status with a balance of ${balance} {currency}. "
                        "If the balance is zero or the status shows paid, confirm the invoice "
                        "has been settled. Thank them for calling."
                    )
                )
            elif inquiry_type == "dispute or discrepancy":
                self.hangup(
                    final_instructions=(
                        f"Acknowledge the caller's dispute about invoice {tran_id} for "
                        f"${balance} {currency}. Let them know their concern has been noted and "
                        "our accounts receivable team will review and follow up within two "
                        "business days. Apologize for the inconvenience and thank them for "
                        "bringing it to our attention."
                    )
                )
            elif inquiry_type == "need a copy":
                self.hangup(
                    final_instructions=(
                        f"Let the caller know that a copy of invoice {tran_id} will be emailed "
                        "to the address on file within one business day. If they need it sooner, "
                        "offer to have an AR specialist send it right away. Thank them for calling."
                    )
                )
            else:
                self.hangup(
                    final_instructions=(
                        f"Read back the invoice summary: {summary}. "
                        "Offer to transfer them to an accounts receivable specialist for any specific questions. "
                        "Thank them for calling Meridian Solutions."
                    )
                )
        except Exception as e:
            logging.error("NetSuite invoice lookup failed: %s", e)
            self.hangup(
                final_instructions=(
                    "Apologize for a technical issue and let the caller know we were unable "
                    "to retrieve the invoice right now. An accounts receivable specialist will "
                    "follow up shortly. Thank them for their patience."
                )
            )


if __name__ == "__main__":
    logging_utils.configure_logging()
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=InvoiceInquiryController,
    )
