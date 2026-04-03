import guava
import os
import logging
import json
import requests
from requests_oauthlib import OAuth1
from datetime import datetime

logging.basicConfig(level=logging.INFO)

NS_ACCOUNT_ID = os.environ["NETSUITE_ACCOUNT_ID"]
NS_CONSUMER_KEY = os.environ["NETSUITE_CONSUMER_KEY"]
NS_CONSUMER_SECRET = os.environ["NETSUITE_CONSUMER_SECRET"]
NS_TOKEN_KEY = os.environ["NETSUITE_TOKEN_KEY"]
NS_TOKEN_SECRET = os.environ["NETSUITE_TOKEN_SECRET"]

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


def find_customer_by_email(email: str) -> dict | None:
    resp = requests.get(
        f"{REST_BASE}/customer",
        auth=_auth(),
        params={"q": f"email IS {email}", "limit": 1},
        timeout=10,
    )
    resp.raise_for_status()
    items = resp.json().get("items", [])
    if not items:
        return None
    return get_customer(items[0]["id"])


def get_customer(customer_id: str) -> dict | None:
    resp = requests.get(
        f"{REST_BASE}/customer/{customer_id}",
        auth=_auth(),
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def get_open_invoices(customer_id: str) -> list:
    """Returns open invoices for the customer."""
    resp = requests.get(
        f"{REST_BASE}/invoice",
        auth=_auth(),
        params={"q": f"customer.id IS {customer_id} AND status IS Open", "limit": 5},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("items", [])


class CustomerAccountLookupController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Meridian Solutions",
            agent_name="Jordan",
            agent_purpose=(
                "to help customers look up their account information, balance, and open invoices"
            ),
        )

        self.set_task(
            objective=(
                "A customer is calling to look up their account information. Collect their "
                "email address and provide a summary of their account status."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Meridian Solutions. I'm Jordan, and I can pull "
                    "up your account information."
                ),
                guava.Field(
                    key="email",
                    field_type="text",
                    description="Ask for the email address associated with their account.",
                    required=True,
                ),
                guava.Field(
                    key="what_they_need",
                    field_type="multiple_choice",
                    description="Ask what they'd like to know about their account.",
                    choices=[
                        "account balance and credit limit",
                        "list of open invoices",
                        "account contact information",
                        "payment terms",
                    ],
                    required=True,
                ),
            ],
            on_complete=self.look_up_account,
        )

        self.accept_call()

    def look_up_account(self):
        email = (self.get_field("email") or "").strip().lower()
        what_they_need = self.get_field("what_they_need")

        logging.info("NetSuite customer lookup for email: %s", email)

        try:
            customer = find_customer_by_email(email)
        except Exception as e:
            logging.error("Customer lookup failed: %s", e)
            customer = None

        if not customer:
            self.hangup(
                final_instructions=(
                    "Let the caller know we couldn't find an account with that email address. "
                    "Ask them to verify the email or try the one they used when signing up. "
                    "Offer to transfer them to an account representative for help. "
                    "Thank them for calling."
                )
            )
            return

        company_name = customer.get("companyname", "")
        first_name = customer.get("firstname", "")
        last_name = customer.get("lastname", "")
        name = company_name or f"{first_name} {last_name}".strip()
        credit_limit = customer.get("creditlimit", "")
        balance = customer.get("balance", "")
        currency = customer.get("currency", {}).get("refName", "USD") if isinstance(customer.get("currency"), dict) else "USD"
        terms = customer.get("terms", {}).get("refName", "") if isinstance(customer.get("terms"), dict) else ""
        phone = customer.get("phone", "")
        address = customer.get("defaultaddress", "")

        result = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "agent": "Jordan",
            "use_case": "customer_account_lookup",
            "email": email,
            "what_they_need": what_they_need,
            "account": {
                "name": name,
                "balance": balance,
                "credit_limit": credit_limit,
                "currency": currency,
                "terms": terms,
            },
        }
        print(json.dumps(result, indent=2))

        if what_they_need == "account balance and credit limit":
            balance_note = f"${balance} {currency}" if balance else "zero"
            limit_note = f"${credit_limit} {currency}" if credit_limit else "not set"
            self.hangup(
                final_instructions=(
                    f"Let the caller know that the account for {name} has a current balance "
                    f"of {balance_note} and a credit limit of {limit_note}. "
                    "If they have questions about specific charges, offer to transfer them to "
                    "an accounts receivable specialist. Thank them for calling."
                )
            )
        elif what_they_need == "list of open invoices":
            try:
                customer_id = customer.get("id", "")
                open_invoices = get_open_invoices(customer_id)
            except Exception as e:
                logging.warning("Failed to fetch open invoices: %s", e)
                open_invoices = []

            if not open_invoices:
                self.hangup(
                    final_instructions=(
                        f"Let {name} know they have no open invoices on their account. "
                        "Thank them for calling Meridian Solutions."
                    )
                )
            else:
                count = len(open_invoices)
                inv_summaries = [
                    f"Invoice {i.get('tranid', i.get('id', ''))} for ${i.get('amountremaining', '')}"
                    for i in open_invoices[:3]
                ]
                self.hangup(
                    final_instructions=(
                        f"Let {name} know they have {count} open invoice(s) on their account. "
                        f"The most recent: {'; '.join(inv_summaries)}. "
                        "If they'd like to pay or dispute any of these, offer to transfer them "
                        "to accounts receivable. Thank them for calling."
                    )
                )
        elif what_they_need == "account contact information":
            self.hangup(
                final_instructions=(
                    f"Let the caller know that the contact information on file for {name} is: "
                    f"phone {phone or 'not on file'}, address: {address or 'not on file'}. "
                    "If they need to update this, let them know an account representative can "
                    "help. Thank them for calling Meridian Solutions."
                )
            )
        elif what_they_need == "payment terms":
            terms_note = terms or "not specified"
            self.hangup(
                final_instructions=(
                    f"Let {name} know their payment terms are: {terms_note}. "
                    "If they have questions about their terms or would like to discuss "
                    "adjustments, offer to connect them with their account manager. "
                    "Thank them for calling."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Give {name} a summary of their account: balance ${balance} {currency}, "
                    f"credit limit ${credit_limit} {currency}, payment terms {terms or 'not specified'}. "
                    "Thank them for calling Meridian Solutions."
                )
            )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=CustomerAccountLookupController,
    )
