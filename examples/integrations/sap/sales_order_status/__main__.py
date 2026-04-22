import guava
import os
import logging
from guava import logging_utils
import json
import requests
from datetime import datetime, timezone


SAP_BASE_URL = os.environ["SAP_BASE_URL"]  # e.g. https://mycompany.s4hana.cloud.sap
SAP_CLIENT_ID = os.environ["SAP_CLIENT_ID"]
SAP_CLIENT_SECRET = os.environ["SAP_CLIENT_SECRET"]
SAP_TOKEN_URL = os.environ["SAP_TOKEN_URL"]  # OAuth token endpoint


def get_access_token() -> str:
    resp = requests.post(
        SAP_TOKEN_URL,
        data={"grant_type": "client_credentials"},
        auth=(SAP_CLIENT_ID, SAP_CLIENT_SECRET),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def find_sales_orders(sold_to_party: str = None, order_id: str = None) -> list:
    """Queries the SAP Sales Order OData API by customer number or order ID."""
    token = get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    base = f"{SAP_BASE_URL}/sap/opu/odata/sap/API_SALES_ORDER_SRV/A_SalesOrder"

    if order_id:
        url = f"{base}('{order_id}')"
        params = {"$expand": "to_Item", "$format": "json"}
    elif sold_to_party:
        url = base
        params = {
            "$filter": f"SoldToParty eq '{sold_to_party}'",
            "$orderby": "CreationDate desc",
            "$top": "5",
            "$expand": "to_Item",
            "$format": "json",
        }
    else:
        return []

    resp = requests.get(url, headers=headers, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json().get("d", {})
    if order_id:
        return [data] if data else []
    return data.get("results", [])


def format_order_summary(order: dict) -> str:
    order_id = order.get("SalesOrder", "")
    status = order.get("OverallSDProcessStatus", "")
    status_map = {
        "A": "open",
        "B": "partially processed",
        "C": "fully processed",
    }
    status_label = status_map.get(status, status)
    net_amount = order.get("TotalNetAmount", "")
    currency = order.get("TransactionCurrency", "")
    created = order.get("CreationDate", "")
    return (
        f"Order {order_id}: {status_label}, "
        f"total {net_amount} {currency}, created {created}"
    )


agent = guava.Agent(
    name="Jamie",
    organization="Apex Industrial Supply",
    purpose="to help customers check the status of their sales orders in our SAP system",
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "look_up_orders",
        objective=(
            "A customer is calling to check on their order status. Collect their "
            "account number or order number and look it up in SAP."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Apex Industrial Supply. I'm Jamie, and I can "
                "look up your order status right now."
            ),
            guava.Field(
                key="lookup_type",
                field_type="multiple_choice",
                description=(
                    "Ask whether they have a specific sales order number, or if they'd "
                    "like to look up all recent orders by their customer account number."
                ),
                choices=["specific order number", "customer account number"],
                required=True,
            ),
            guava.Field(
                key="order_or_account",
                field_type="text",
                description=(
                    "Ask them to provide the order number or customer account number "
                    "depending on what they selected. Capture the number exactly as stated."
                ),
                required=True,
            ),
        ],
    )


@agent.on_task_complete("look_up_orders")
def on_done(call: guava.Call) -> None:
    lookup_type = call.get_field("lookup_type")
    identifier = call.get_field("order_or_account") or ""

    logging.info("SAP order lookup — type: %s, id: %s", lookup_type, identifier)

    by_order_id = lookup_type == "specific order number"

    try:
        if by_order_id:
            orders = find_sales_orders(order_id=identifier.strip())
        else:
            orders = find_sales_orders(sold_to_party=identifier.strip())

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "Jamie",
            "use_case": "sales_order_status",
            "lookup_type": lookup_type,
            "identifier": identifier,
            "orders_found": len(orders),
            "orders": [
                {
                    "SalesOrder": o.get("SalesOrder"),
                    "OverallSDProcessStatus": o.get("OverallSDProcessStatus"),
                    "TotalNetAmount": o.get("TotalNetAmount"),
                    "TransactionCurrency": o.get("TransactionCurrency"),
                    "CreationDate": o.get("CreationDate"),
                }
                for o in orders
            ],
        }
        print(json.dumps(result, indent=2))

        if not orders:
            call.hangup(
                final_instructions=(
                    f"Let the caller know that no orders were found for "
                    f"{'order number' if by_order_id else 'account number'} {identifier}. "
                    "Ask them to double-check the number, or offer to transfer them to a "
                    "customer service representative. Thank them for calling."
                )
            )
            return

        if by_order_id:
            summary = format_order_summary(orders[0])
            items = orders[0].get("to_Item", {}).get("results", [])
            item_count = len(items)
            item_note = f" It contains {item_count} line item(s)." if item_count else ""
            call.hangup(
                final_instructions=(
                    f"Let the caller know the status of their order: {summary}.{item_note} "
                    "If they have questions about a specific line item or need to make a "
                    "change, offer to connect them with a customer service representative. "
                    "Thank them for calling Apex Industrial Supply."
                )
            )
        else:
            summaries = [format_order_summary(o) for o in orders[:3]]
            summary_text = "; ".join(summaries)
            total = len(orders)
            count_note = f"Your {total} most recent order(s): " if total > 1 else "Your most recent order: "
            call.hangup(
                final_instructions=(
                    f"Let the caller know we found {total} recent order(s) on their account. "
                    f"{count_note}{summary_text}. "
                    "If they need details on a specific order, ask them for the order number "
                    "and offer to look it up. Thank them for calling Apex Industrial Supply."
                )
            )
    except Exception as e:
        logging.error("SAP order lookup failed: %s", e)
        call.hangup(
            final_instructions=(
                "Apologize for a technical issue and let the caller know we were unable to "
                "retrieve the order information at this time. A customer service representative "
                "will follow up with them shortly. Thank them for their patience."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
