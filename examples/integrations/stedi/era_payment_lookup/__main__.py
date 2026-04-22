import logging
import os

import guava
import requests
from guava import logging_utils

STEDI_API_KEY = os.environ["STEDI_API_KEY"]
BASE_URL = "https://healthcare.us.stedi.com/2024-04-01"
HEADERS = {
    "Authorization": f"Key {STEDI_API_KEY}",
    "Content-Type": "application/json",
}


def get_era_report(transaction_id: str) -> dict:
    """Retrieves an 835 ERA remittance report for the given Stedi transaction ID."""
    resp = requests.get(
        f"{BASE_URL}/change/medicalnetwork/reports/v2/{transaction_id}/835",
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def summarize_era(report: dict) -> dict:
    """Extracts key payment fields from an 835 ERA report."""
    financial_info = report.get("financialInformation", {})
    payer_name = report.get("payerIdentification", {}).get("name", "Unknown Payer")
    payment_date = financial_info.get("transactionHandlingDate", "")
    payment_amount = financial_info.get("transactionAmount", "")
    payment_method = financial_info.get("creditDebitFlagCode", "")

    claims = []
    for claim in report.get("claimPaymentInformation", []):
        claims.append(
            {
                "claim_number": claim.get("patientControlNumber", ""),
                "patient": claim.get("patientName", ""),
                "billed": claim.get("totalClaimChargeAmount"),
                "paid": claim.get("claimPaymentAmount"),
                "status": claim.get("claimStatusCode", ""),
            }
        )

    return {
        "payer_name": payer_name,
        "payment_date": payment_date,
        "payment_amount": payment_amount,
        "payment_method": payment_method,
        "claims": claims,
    }


agent = guava.Agent(
    name="Morgan",
    organization="Ridgeline Health",
    purpose=(
        "to help billing staff retrieve electronic remittance advice (ERA) payment details "
        "for specific insurance transactions"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "retrieve_era",
        objective=(
            "A billing team member has called to look up payment details from an 835 ERA. "
            "Collect the Stedi transaction ID and retrieve the remittance summary."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Ridgeline Health billing support. I'm Morgan. "
                "I can pull up ERA payment details — I'll just need the Stedi transaction ID."
            ),
            guava.Field(
                key="transaction_id",
                field_type="text",
                description=(
                    "Ask for the Stedi transaction ID for the 835 ERA they want to look up. "
                    "This is found in the Stedi portal or the transaction log."
                ),
                required=True,
            ),
        ],
    )


@agent.on_task_complete("retrieve_era")
def retrieve_era(call: guava.Call) -> None:
    transaction_id = (call.get_field("transaction_id") or "").strip()
    logging.info("Retrieving 835 ERA for transaction: %s", transaction_id)

    try:
        report = get_era_report(transaction_id)
        summary = summarize_era(report)
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            call.hangup(
                final_instructions=(
                    f"Let the caller know that no 835 ERA was found for transaction ID "
                    f"'{transaction_id}'. Ask them to double-check the ID in the Stedi portal "
                    "and try again."
                )
            )
            return
        logging.error("Stedi ERA lookup failed: %s", e)
        call.hangup(
            final_instructions=(
                "Apologize — there was a technical issue retrieving the ERA. "
                "Ask the caller to check the Stedi portal directly or try again shortly."
            )
        )
        return
    except Exception as e:
        logging.error("Stedi ERA lookup failed: %s", e)
        call.hangup(
            final_instructions=(
                "Apologize — there was a technical issue retrieving the ERA. "
                "Ask the caller to check the Stedi portal directly or try again shortly."
            )
        )
        return

    payer = summary["payer_name"]
    payment_date = summary["payment_date"]
    payment_amount = summary["payment_amount"]
    payment_method = summary["payment_method"]
    claims = summary["claims"]

    claim_count = len(claims)
    try:
        total_paid = sum(float(c["paid"]) for c in claims if c.get("paid"))
    except (TypeError, ValueError):
        total_paid = 0.0

    claims_summary = (
        f"{claim_count} claim{'s' if claim_count != 1 else ''} covered, "
        f"total paid: ${total_paid:,.2f}"
        if claims
        else "no individual claim details available"
    )

    logging.info(
        "ERA summary — payer: %s, date: %s, amount: %s, claims: %d",
        payer, payment_date, payment_amount, claim_count,
    )

    amount_str = ""
    if payment_amount:
        try:
            amount_str = f"Payment amount: ${float(payment_amount):,.2f}. "
        except (TypeError, ValueError):
            amount_str = f"Payment amount: {payment_amount}. "

    call.hangup(
        final_instructions=(
            f"Share the ERA details for transaction {transaction_id}: "
            f"This is an 835 remittance from {payer}. "
            + (f"Payment date: {payment_date}. " if payment_date else "")
            + amount_str
            + (f"Payment method code: {payment_method}. " if payment_method else "")
            + f"{claims_summary}. "
            "Let them know full line-item details are available in the Stedi portal. "
            "Thank them for calling."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
