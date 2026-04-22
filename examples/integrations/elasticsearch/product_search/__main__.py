import logging
import os

import guava
import requests
from guava import logging_utils

ES_URL = os.environ["ELASTICSEARCH_URL"].rstrip("/")
PRODUCT_INDEX = os.environ.get("ELASTICSEARCH_PRODUCT_INDEX", "products")


def get_headers() -> dict:
    return {
        "Authorization": f"ApiKey {os.environ['ELASTICSEARCH_API_KEY']}",
        "Content-Type": "application/json",
    }


def search_products(query: str, max_price: float | None = None, category: str = "") -> list[dict]:
    must: list[dict] = [
        {
            "multi_match": {
                "query": query,
                "fields": ["name^3", "description", "category", "brand"],
                "fuzziness": "AUTO",
            }
        }
    ]
    filters: list[dict] = []
    if max_price is not None:
        filters.append({"range": {"price": {"lte": max_price}}})
    if category:
        filters.append({"term": {"category.keyword": category}})

    body: dict = {
        "query": {
            "bool": {
                "must": must,
                "filter": filters,
            }
        },
        "size": 5,
        "_source": ["name", "description", "price", "category", "brand", "in_stock", "sku"],
    }

    resp = requests.post(
        f"{ES_URL}/{PRODUCT_INDEX}/_search",
        headers=get_headers(),
        json=body,
        timeout=10,
    )
    resp.raise_for_status()
    hits = resp.json().get("hits", {}).get("hits", [])
    return [h["_source"] for h in hits]


agent = guava.Agent(
    name="Morgan",
    organization="Apex Store",
    purpose="to help Apex Store customers find products by phone",
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "product_search",
        objective=(
            "A customer has called to search for products. "
            "Collect their search query, optional price limit, and category filter, "
            "then search and read back the top results."
        ),
        checklist=[
            guava.Say(
                "Welcome to Apex Store. This is Morgan. I can help you find a product today."
            ),
            guava.Field(
                key="search_query",
                field_type="text",
                description="Ask what product they're looking for.",
                required=True,
            ),
            guava.Field(
                key="max_price",
                field_type="text",
                description="Ask if they have a maximum budget in mind (optional).",
                required=False,
            ),
            guava.Field(
                key="category",
                field_type="text",
                description="Ask if they want to filter by a specific category (optional).",
                required=False,
            ),
        ],
    )


@agent.on_task_complete("product_search")
def on_done(call: guava.Call) -> None:
    search_query = call.get_field("search_query") or ""
    max_price_str = call.get_field("max_price") or ""
    category = call.get_field("category") or ""

    max_price = None
    if max_price_str:
        try:
            max_price = float(max_price_str.replace("$", "").replace(",", ""))
        except ValueError:
            pass

    logging.info("Searching products: query=%s, max_price=%s, category=%s", search_query, max_price, category)

    products = []
    try:
        products = search_products(search_query, max_price=max_price, category=category)
        logging.info("Found %d products", len(products))
    except Exception as e:
        logging.error("Failed to search products: %s", e)

    if not products:
        call.hangup(
            final_instructions=(
                f"Let the customer know no products were found matching '{search_query}'. "
                "Suggest they try a different search term or visit the website for the full catalog. "
                "Thank them for calling Apex Store."
            )
        )
        return

    product_list = "; ".join(
        f"{p.get('name', 'Unknown')} — ${p.get('price', 0):.2f}"
        + (f" ({p.get('category', '')})" if p.get("category") else "")
        + (" [in stock]" if p.get("in_stock") else " [out of stock]")
        for p in products[:3]
    )

    call.hangup(
        final_instructions=(
            f"Read the following top product results to the customer: {product_list}. "
            "Mention that they can call back if they'd like to narrow the search further. "
            "Thank them for calling Apex Store."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
