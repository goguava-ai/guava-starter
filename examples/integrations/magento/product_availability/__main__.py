import guava
import os
import logging
from guava import logging_utils
import json
import requests
from datetime import datetime, timezone


MAGENTO_BASE_URL = os.environ["MAGENTO_BASE_URL"]
MAGENTO_ACCESS_TOKEN = os.environ["MAGENTO_ACCESS_TOKEN"]

HEADERS = {
    "Authorization": f"Bearer {MAGENTO_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}
REST_BASE = f"{MAGENTO_BASE_URL}/rest/V1"


def search_products(query: str) -> list:
    """Full-text search for products by name or SKU."""
    resp = requests.get(
        f"{REST_BASE}/products",
        headers=HEADERS,
        params={
            "searchCriteria[filter_groups][0][filters][0][field]": "name",
            "searchCriteria[filter_groups][0][filters][0][value]": f"%{query}%",
            "searchCriteria[filter_groups][0][filters][0][condition_type]": "like",
            "searchCriteria[pageSize]": "5",
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("items", [])


def get_product_stock(sku: str) -> dict | None:
    """Returns stock item data for a given SKU."""
    resp = requests.get(
        f"{REST_BASE}/stockItems/{sku}",
        headers=HEADERS,
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def get_product_by_sku(sku: str) -> dict | None:
    resp = requests.get(
        f"{REST_BASE}/products/{sku}",
        headers=HEADERS,
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


agent = guava.Agent(
    name="Riley",
    organization="Prestige Home Goods",
    purpose="to help customers check whether a product is in stock and available to order",
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "collect_product_info",
        objective=(
            "A customer is calling to check whether a specific product is available. "
            "Collect the product name or SKU and check stock status."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Prestige Home Goods. I'm Riley. "
                "I can check product availability for you."
            ),
            guava.Field(
                key="product_query",
                field_type="text",
                description=(
                    "Ask the customer to describe the product they're looking for. "
                    "They can give a product name, SKU, or a brief description. Capture it."
                ),
                required=True,
            ),
            guava.Field(
                key="have_sku",
                field_type="multiple_choice",
                description="Ask if they have the specific SKU or item number from the website.",
                choices=["yes, I have the SKU", "no, just the product name"],
                required=True,
            ),
            guava.Field(
                key="sku",
                field_type="text",
                description=(
                    "If they have the SKU, ask them to provide it now. "
                    "Skip if they said no."
                ),
                required=False,
            ),
        ],
    )


@agent.on_task_complete("collect_product_info")
def check_availability(call: guava.Call) -> None:
    product_query = call.get_field("product_query") or ""
    have_sku = call.get_field("have_sku")
    sku = (call.get_field("sku") or "").strip()

    logging.info(
        "Product availability check — query: %s, sku: %s", product_query, sku
    )

    try:
        if have_sku == "yes, I have the SKU" and sku:
            product = get_product_by_sku(sku)
            products = [product] if product else []
        else:
            products = search_products(product_query)

        if not products:
            call.hangup(
                final_instructions=(
                    f"Let the caller know we couldn't find a product matching "
                    f"'{product_query}' in our catalog. Suggest they visit our website "
                    "to browse the full catalog or speak with a product specialist. "
                    "Thank them for calling Prestige Home Goods."
                )
            )
            return

        product = products[0]
        product_name = product.get("name", "")
        product_sku = product.get("sku", "")
        price = product.get("price", "")
        status = product.get("status", 1)  # 1=enabled, 2=disabled

        # Fetch stock information
        stock = None
        try:
            stock = get_product_stock(product_sku)
        except Exception as e:
            logging.warning("Could not fetch stock for %s: %s", product_sku, e)

        is_in_stock = stock.get("is_in_stock", False) if stock else False
        qty = stock.get("qty", 0) if stock else 0

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "Riley",
            "use_case": "product_availability",
            "query": product_query,
            "product": {
                "name": product_name,
                "sku": product_sku,
                "price": price,
                "in_stock": is_in_stock,
                "qty": qty,
            },
        }
        print(json.dumps(result, indent=2))

        price_note = f" It's priced at ${price}." if price else ""

        if status == 2:
            call.hangup(
                final_instructions=(
                    f"Let the caller know that '{product_name}' is currently not available "
                    "in our catalog. Suggest they visit our website to see similar products "
                    "or sign up for restock notifications. "
                    "Thank them for calling Prestige Home Goods."
                )
            )
        elif is_in_stock and qty > 0:
            qty_note = f" We currently have {int(qty)} unit(s) available." if qty < 10 else ""
            call.hangup(
                final_instructions=(
                    f"Let the caller know that '{product_name}' (SKU: {product_sku}) is "
                    f"currently in stock.{price_note}{qty_note} "
                    "They can order it on our website or call back to place an order over the phone. "
                    "Thank them for calling Prestige Home Goods."
                )
            )
        else:
            call.hangup(
                final_instructions=(
                    f"Let the caller know that '{product_name}' is currently out of stock.{price_note} "
                    "Let them know they can sign up for restock notifications on the product "
                    "page on our website or offer to suggest a similar in-stock alternative. "
                    "Thank them for calling Prestige Home Goods."
                )
            )
    except Exception as e:
        logging.error("Product availability check failed: %s", e)
        call.hangup(
            final_instructions=(
                "Apologize for a technical issue and let the caller know we were unable "
                "to check availability right now. Suggest they visit the website or call "
                "back shortly. Thank them for their patience."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
