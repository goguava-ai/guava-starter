import guava
import os
import logging
from guava import logging_utils
from pymongo import MongoClient


_client = MongoClient(os.environ["MONGODB_URI"])
_db = _client[os.environ["MONGODB_DATABASE"]]
products = _db["products"]


def search_products(
    category: str,
    max_price: float | None,
    in_stock_only: bool,
) -> list[dict]:
    """
    Queries the products collection for matching items.
    Returns up to 5 results sorted by rating descending.
    """
    query: dict = {}

    if category and category != "any":
        query["category"] = {"$regex": category, "$options": "i"}

    if max_price is not None:
        query["price"] = {"$lte": max_price}

    if in_stock_only:
        query["in_stock"] = True

    cursor = (
        products.find(query, {"_id": 0, "name": 1, "category": 1, "price": 1, "rating": 1, "short_description": 1})
        .sort("rating", -1)
        .limit(5)
    )
    return list(cursor)


def format_product(p: dict) -> str:
    price = f"${p.get('price', 0):,.2f}"
    rating = p.get("rating")
    rating_str = f" — rated {rating}/5" if rating else ""
    desc = p.get("short_description") or ""
    return f"{p.get('name', 'Unknown')} ({price}){rating_str}" + (f": {desc}" if desc else "")


PRICE_LIMITS = {
    "under $25": 25,
    "under $50": 50,
    "under $100": 100,
    "under $250": 250,
    "no limit": None,
}


agent = guava.Agent(
    name="Jordan",
    organization="Vantage",
    purpose=(
        "to help Vantage customers find the right product in the catalog "
        "based on their needs and budget"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "product_search",
        objective=(
            "A customer has called to find a product. "
            "Understand what they're looking for, search the catalog, "
            "and recommend the best matches."
        ),
        checklist=[
            guava.Say(
                "Thanks for calling Vantage. I'm Jordan. "
                "I'd love to help you find exactly what you're looking for. "
                "Let me ask you a couple of quick questions."
            ),
            guava.Field(
                key="category",
                field_type="multiple_choice",
                description="Ask what type of product they're looking for.",
                choices=[
                    "analytics",
                    "monitoring",
                    "security",
                    "automation",
                    "integration",
                    "any",
                ],
                required=True,
            ),
            guava.Field(
                key="use_case",
                field_type="text",
                description=(
                    "Ask what they're trying to accomplish — the more specific the better. "
                    "Capture their answer."
                ),
                required=True,
            ),
            guava.Field(
                key="budget",
                field_type="multiple_choice",
                description="Ask if they have a budget in mind.",
                choices=list(PRICE_LIMITS.keys()),
                required=False,
            ),
            guava.Field(
                key="in_stock_only",
                field_type="multiple_choice",
                description="Ask if they need something available immediately.",
                choices=["yes, in stock only", "no, show me everything"],
                required=False,
            ),
        ],
    )


@agent.on_task_complete("product_search")
def on_product_search_done(call: guava.Call) -> None:
    category = call.get_field("category") or "any"
    use_case = call.get_field("use_case") or ""
    budget_str = call.get_field("budget") or "no limit"
    in_stock_pref = call.get_field("in_stock_only") or ""

    max_price = PRICE_LIMITS.get(budget_str)
    in_stock_only = "in stock only" in in_stock_pref

    logging.info(
        "Searching products: category=%s, max_price=%s, in_stock=%s",
        category, max_price, in_stock_only,
    )

    try:
        results = search_products(category, max_price, in_stock_only)
    except Exception as e:
        logging.error("Product search failed: %s", e)
        results = []

    if not results:
        call.hangup(
            final_instructions=(
                "Let the caller know you didn't find any products matching their criteria. "
                "Suggest they try broadening the category or budget, or offer to connect "
                "them with a product specialist who can recommend alternatives."
            )
        )
        return

    top = results[0]
    top_str = format_product(top)
    others = results[1:]
    others_str = "; ".join(format_product(p) for p in others)

    logging.info("Found %d matching products", len(results))

    call.hangup(
        final_instructions=(
            f"Let the caller know you found {len(results)} matching product(s). "
            f"Your top recommendation based on their needs ({use_case}) and budget is: {top_str}. "
            + (f"Other strong options: {others_str}. " if others else "")
            + "Mention that they can call back if they'd like to narrow the search further. "
            "Offer to connect them with a product specialist for a deeper recommendation."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
