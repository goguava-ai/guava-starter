import json
import logging
import os
from datetime import datetime, timezone

import guava
import requests
from guava import logging_utils
from requests_oauthlib import OAuth1

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


def find_po_by_number(po_number: str) -> dict | None:
    """Searches for a purchase order by tranid (transaction/PO number)."""
    resp = requests.get(
        f"{REST_BASE}/purchaseOrder",
        auth=_auth(),
        params={"q": f"tranid IS {po_number}", "limit": 1},
        timeout=10,
    )
    resp.raise_for_status()
    items = resp.json().get("items", [])
    if not items:
        return None
    # Fetch the full record with line items
    po_id = items[0]["id"]
    detail_resp = requests.get(
        f"{REST_BASE}/purchaseOrder/{po_id}",
        auth=_auth(),
        params={"expandSubResources": "true"},
        timeout=10,
    )
    detail_resp.raise_for_status()
    return detail_resp.json()


def find_pos_by_vendor(vendor_name: str) -> list:
    """Searches for open POs for a given vendor by name."""
    resp = requests.get(
        f"{REST_BASE}/purchaseOrder",
        auth=_auth(),
        params={
            "q": f"vendor.entityid CONTAINS {vendor_name} AND status IS Open",
            "limit": 5,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("items", [])


def format_po_summary(po: dict) -> str:
    tran_id = po.get("tranid", "")
    status = po.get("status", {}).get("refName", "") if isinstance(po.get("status"), dict) else po.get("status", "")
    total = po.get("total", "")
    currency = po.get("currency", {}).get("refName", "USD") if isinstance(po.get("currency"), dict) else "USD"
    expected_date = po.get("shipdate", "") or po.get("duedate", "")
    return f"PO {tran_id}: {status}, ${total} {currency}, expected {expected_date}"


agent = guava.Agent(
    name="Morgan",
    organization="Meridian Solutions",
    purpose=(
        "to help vendors and internal procurement staff check the status of "
        "purchase orders in our NetSuite system"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "purchase_order_status",
        objective=(
            "A caller wants to check purchase order status. Collect the PO number or "
            "vendor name and look it up in NetSuite."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Meridian Solutions procurement. I'm Morgan. "
                "I can look up purchase order status for you."
            ),
            guava.Field(
                key="lookup_type",
                field_type="multiple_choice",
                description=(
                    "Ask whether they have a specific PO number or would like to search "
                    "by vendor name."
                ),
                choices=["PO number", "vendor name"],
                required=True,
            ),
            guava.Field(
                key="identifier",
                field_type="text",
                description="Ask for the PO number or vendor name.",
                required=True,
            ),
        ],
    )


@agent.on_task_complete("purchase_order_status")
def on_purchase_order_status_done(call: guava.Call) -> None:
    lookup_type = call.get_field("lookup_type")
    identifier = (call.get_field("identifier") or "").strip()
    by_po = lookup_type == "PO number"

    logging.info("NetSuite PO lookup — type: %s, id: %s", lookup_type, identifier)

    try:
        if by_po:
            po = find_po_by_number(identifier)
            pos = [po] if po else []
        else:
            pos = find_pos_by_vendor(identifier)

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "Morgan",
            "use_case": "purchase_order_status",
            "lookup_type": lookup_type,
            "identifier": identifier,
            "pos_found": len(pos),
        }
        print(json.dumps(result, indent=2))

        if not pos:
            call.hangup(
                final_instructions=(
                    f"Let the caller know we couldn't find any purchase orders for "
                    f"{'PO number' if by_po else 'vendor'} {identifier}. "
                    "Ask them to verify and call back, or offer to transfer them to "
                    "a procurement specialist. Thank them for calling."
                )
            )
            return

        if by_po:
            po = pos[0]
            summary = format_po_summary(po)
            # Check if items have been received
            items = po.get("item", {}).get("items", []) if isinstance(po.get("item"), dict) else []
            received_items = [i for i in items if i.get("quantityreceived", 0) > 0]
            receipt_note = ""
            if received_items:
                receipt_note = (
                    f" {len(received_items)} of {len(items)} line item(s) have been received."
                )
            call.hangup(
                final_instructions=(
                    f"Let the caller know the purchase order status: {summary}.{receipt_note} "
                    "If they have questions about specific line items or need to update the PO, "
                    "offer to connect them with a procurement specialist. "
                    "Thank them for calling Meridian Solutions."
                )
            )
        else:
            summaries = [format_po_summary(p) for p in pos[:3]]
            summary_text = "; ".join(summaries)
            call.hangup(
                final_instructions=(
                    f"Let the caller know we found {len(pos)} open purchase order(s) for "
                    f"vendor '{identifier}'. The most recent: {summary_text}. "
                    "If they need details on a specific PO, offer to look it up by PO number. "
                    "Thank them for calling Meridian Solutions."
                )
            )
    except Exception as e:
        logging.error("NetSuite PO lookup failed: %s", e)
        call.hangup(
            final_instructions=(
                "Apologize for a technical issue and let the caller know we were unable to "
                "retrieve purchase order information right now. A procurement specialist "
                "will follow up shortly. Thank them for their patience."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
