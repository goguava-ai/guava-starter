import guava
import os
import logging
import json
import requests
from datetime import datetime

logging.basicConfig(level=logging.INFO)

SAP_BASE_URL = os.environ["SAP_BASE_URL"]
SAP_CLIENT_ID = os.environ["SAP_CLIENT_ID"]
SAP_CLIENT_SECRET = os.environ["SAP_CLIENT_SECRET"]
SAP_TOKEN_URL = os.environ["SAP_TOKEN_URL"]


def get_access_token() -> str:
    resp = requests.post(
        SAP_TOKEN_URL,
        data={"grant_type": "client_credentials"},
        auth=(SAP_CLIENT_ID, SAP_CLIENT_SECRET),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def get_purchase_order(po_number: str) -> dict | None:
    """Fetches a purchase order from the SAP Purchase Order OData API."""
    token = get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    url = (
        f"{SAP_BASE_URL}/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV"
        f"/A_PurchaseOrder('{po_number}')"
    )
    resp = requests.get(
        url,
        headers=headers,
        params={"$expand": "to_PurchaseOrderItem", "$format": "json"},
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json().get("d")


def find_po_by_vendor(vendor_id: str) -> list:
    """Returns the 5 most recent open POs for a given vendor."""
    token = get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    url = f"{SAP_BASE_URL}/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV/A_PurchaseOrder"
    resp = requests.get(
        url,
        headers=headers,
        params={
            "$filter": f"Supplier eq '{vendor_id}' and PurchaseOrderStatus eq 'B'",
            "$orderby": "CreationDate desc",
            "$top": "5",
            "$format": "json",
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("d", {}).get("results", [])


def format_po_summary(po: dict) -> str:
    po_id = po.get("PurchaseOrder", "")
    status_map = {
        "": "draft",
        "A": "open",
        "B": "in process",
        "C": "closed",
    }
    status = status_map.get(po.get("PurchaseOrderStatus", ""), po.get("PurchaseOrderStatus", ""))
    amount = po.get("NetAmount", "")
    currency = po.get("DocumentCurrency", "")
    created = po.get("CreationDate", "")
    return f"PO {po_id}: {status}, {amount} {currency}, created {created}"


class PurchaseOrderStatusController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Apex Industrial Supply",
            agent_name="Sam",
            agent_purpose=(
                "to help vendors and procurement staff check the status of purchase orders "
                "in our SAP system"
            ),
        )

        self.set_task(
            objective=(
                "A vendor or procurement staff member is calling to check purchase order status. "
                "Collect their PO number or vendor account number and look it up in SAP."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Apex Industrial Supply procurement. "
                    "I'm Sam, and I can look up purchase order status for you."
                ),
                guava.Field(
                    key="lookup_type",
                    field_type="multiple_choice",
                    description=(
                        "Ask whether they have a specific PO number they'd like to look up, "
                        "or if they'd like to see all open POs by vendor account number."
                    ),
                    choices=["specific PO number", "vendor account number"],
                    required=True,
                ),
                guava.Field(
                    key="identifier",
                    field_type="text",
                    description=(
                        "Ask for the PO number or vendor account number they'd like to look up."
                    ),
                    required=True,
                ),
            ],
            on_complete=self.look_up_po,
        )

        self.accept_call()

    def look_up_po(self):
        lookup_type = self.get_field("lookup_type")
        identifier = (self.get_field("identifier") or "").strip()
        by_po = lookup_type == "specific PO number"

        logging.info("SAP PO lookup — type: %s, id: %s", lookup_type, identifier)

        try:
            if by_po:
                po = get_purchase_order(identifier)
                orders = [po] if po else []
            else:
                orders = find_po_by_vendor(identifier)

            result = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "agent": "Sam",
                "use_case": "purchase_order_status",
                "lookup_type": lookup_type,
                "identifier": identifier,
                "orders_found": len(orders),
                "orders": [
                    {
                        "PurchaseOrder": o.get("PurchaseOrder"),
                        "PurchaseOrderStatus": o.get("PurchaseOrderStatus"),
                        "NetAmount": o.get("NetAmount"),
                        "DocumentCurrency": o.get("DocumentCurrency"),
                        "CreationDate": o.get("CreationDate"),
                        "SupplierOrderID": o.get("SupplierOrderID"),
                    }
                    for o in orders
                ],
            }
            print(json.dumps(result, indent=2))

            if not orders:
                self.hangup(
                    final_instructions=(
                        f"Let the caller know no purchase orders were found for "
                        f"{'PO number' if by_po else 'vendor account'} {identifier}. "
                        "Ask them to verify the number and call back, or offer to transfer "
                        "them to a procurement specialist. Thank them for calling."
                    )
                )
                return

            if by_po:
                po = orders[0]
                summary = format_po_summary(po)
                items = po.get("to_PurchaseOrderItem", {}).get("results", [])
                item_count = len(items)
                item_note = f" The PO contains {item_count} line item(s)." if item_count else ""
                delivery_date = ""
                if items:
                    delivery_date = items[0].get("ScheduleLineDeliveryDate", "")
                delivery_note = f" The scheduled delivery date is {delivery_date}." if delivery_date else ""
                self.hangup(
                    final_instructions=(
                        f"Let the caller know the status of their purchase order: {summary}."
                        f"{item_note}{delivery_note} "
                        "If they have questions about specific line items or delivery, offer to "
                        "connect them with a procurement specialist. "
                        "Thank them for calling Apex Industrial Supply."
                    )
                )
            else:
                summaries = [format_po_summary(o) for o in orders[:3]]
                summary_text = "; ".join(summaries)
                self.hangup(
                    final_instructions=(
                        f"Let the caller know we found {len(orders)} open purchase order(s) for "
                        f"their vendor account. The most recent: {summary_text}. "
                        "If they need details on a specific PO, offer to look it up by PO number. "
                        "Thank them for calling Apex Industrial Supply."
                    )
                )
        except Exception as e:
            logging.error("SAP PO lookup failed: %s", e)
            self.hangup(
                final_instructions=(
                    "Apologize for a technical issue and let the caller know we were unable to "
                    "retrieve the purchase order information right now. A procurement specialist "
                    "will follow up shortly. Thank them for their patience."
                )
            )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=PurchaseOrderStatusController,
    )
