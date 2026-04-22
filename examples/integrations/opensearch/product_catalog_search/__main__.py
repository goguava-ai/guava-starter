import guava
import os
import logging
from guava import logging_utils
from opensearchpy import OpenSearch, NotFoundError


OPENSEARCH_HOST = os.environ["OPENSEARCH_HOST"]
OPENSEARCH_PORT = int(os.environ.get("OPENSEARCH_PORT", "443"))
OPENSEARCH_USER = os.environ["OPENSEARCH_USER"]
OPENSEARCH_PASSWORD = os.environ["OPENSEARCH_PASSWORD"]
PRODUCTS_INDEX = os.environ.get("OPENSEARCH_PRODUCTS_INDEX", "products")

client = OpenSearch(
    hosts=[{"host": OPENSEARCH_HOST, "port": OPENSEARCH_PORT}],
    http_auth=(OPENSEARCH_USER, OPENSEARCH_PASSWORD),
    use_ssl=True,
    verify_certs=True,
)


def search_products(
    query: str,
    category: str = "",
    max_price: float = 0.0,
    in_stock_only: bool = True,
    top_k: int = 5,
) -> list[dict]:
    """Search the product catalog with optional filters."""
    must_clauses = [
        {
            "multi_match": {
                "query": query,
                "fields": ["name^3", "description^2", "brand", "tags"],
                "type": "best_fields",
                "fuzziness": "AUTO",
            }
        }
    ]

    filters = []
    if in_stock_only:
        filters.append({"term": {"in_stock": True}})
    if category:
        filters.append({"match": {"category": category}})
    if max_price > 0:
        filters.append({"range": {"price": {"lte": max_price}}})

    body: dict = {
        "size": top_k,
        "query": {
            "bool": {
                "must": must_clauses,
                "filter": filters,
            }
        },
        "_source": ["name", "brand", "price", "category", "description", "sku", "in_stock"],
        "sort": [{"_score": "desc"}],
    }

    try:
        response = client.search(index=PRODUCTS_INDEX, body=body)
        return [hit["_source"] for hit in response["hits"]["hits"]]
    except NotFoundError:
        logging.warning("Products index '%s' not found.", PRODUCTS_INDEX)
        return []


def format_product(product: dict) -> str:
    name = product.get("name", "Unknown product")
    brand = product.get("brand", "")
    price = product.get("price")
    price_str = f"${price:.2f}" if price is not None else "price unavailable"
    brand_str = f" by {brand}" if brand else ""
    return f"{name}{brand_str} — {price_str}"


class ProductCatalogSearchController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Horizon Home",
            agent_name="Taylor",
            agent_purpose=(
                "to help Horizon Home customers find products in our catalog by searching "
                "based on what they describe"
            ),
        )

        self.set_task(
            objective=(
                "A customer is looking for a product. Collect their description and any "
                "preferences, search the catalog, and share the best matches."
            ),
            checklist=[
                guava.Say(
                    "Thanks for calling Horizon Home. This is Taylor. "
                    "Tell me what you're looking for and I'll search our catalog for you."
                ),
                guava.Field(
                    key="product_description",
                    field_type="text",
                    description=(
                        "Ask the customer to describe the product they're looking for — "
                        "what it does, any brand preferences, color, size, or other attributes."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="category",
                    field_type="multiple_choice",
                    description="Ask which product category this falls under, if they know.",
                    choices=[
                        "furniture",
                        "kitchen and dining",
                        "bedding and bath",
                        "lighting",
                        "outdoor",
                        "decor and accessories",
                        "not sure",
                    ],
                    required=False,
                ),
                guava.Field(
                    key="max_budget",
                    field_type="text",
                    description=(
                        "Ask if they have a budget or maximum price in mind. "
                        "If they say 'no limit' or don't know, leave it open."
                    ),
                    required=False,
                ),
            ],
            on_complete=self.search_and_present,
        )

        self.accept_call()

    def search_and_present(self):
        description = self.get_field("product_description") or ""
        category = self.get_field("category") or ""
        if category == "not sure":
            category = ""
        budget_str = self.get_field("max_budget") or ""

        max_price = 0.0
        try:
            cleaned = budget_str.replace("$", "").replace(",", "").strip()
            max_price = float(cleaned) if cleaned else 0.0
        except ValueError:
            max_price = 0.0

        logging.info(
            "Searching products: query='%s', category='%s', max_price=%.2f",
            description, category, max_price,
        )

        try:
            products = search_products(
                query=description,
                category=category,
                max_price=max_price,
                in_stock_only=True,
            )
        except Exception as e:
            logging.error("Product catalog search failed: %s", e)
            products = []

        if not products:
            self.hangup(
                final_instructions=(
                    "Let the customer know you didn't find any products matching their description "
                    "in stock right now. Suggest they visit horizonhome.com to browse the full catalog "
                    "or sign up for restock alerts. Offer to note their request for the merchandising team. "
                    "Be warm and helpful."
                )
            )
            return

        product_lines = [format_product(p) for p in products[:3]]
        product_summary = "; ".join(product_lines)
        logging.info("Found %d products for query: %s", len(products), description)

        self.hangup(
            final_instructions=(
                f"Tell the customer you found {len(products)} matching products. "
                f"Read them the top options: {product_summary}. "
                "Describe each one naturally — name, brand, and price. "
                "Let them know they can also browse at horizonhome.com or call back to narrow the search further. "
                "Thank them for calling Horizon Home."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=ProductCatalogSearchController,
    )
