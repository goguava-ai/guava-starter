import guava
import os
import logging
from guava import logging_utils
import pymysql
import pymysql.cursors



def get_connection():
    return pymysql.connect(
        host=os.environ["MYSQL_HOST"],
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=os.environ["MYSQL_USER"],
        password=os.environ["MYSQL_PASSWORD"],
        database=os.environ["MYSQL_DATABASE"],
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def search_products(query: str) -> list[dict]:
    """Search for products by name or SKU. Returns up to 5 matches."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT sku, name, category, price, stock_quantity, location
                FROM products
                WHERE name LIKE %s OR sku = %s
                LIMIT 5
                """,
                (f"%{query}%", query.upper()),
            )
            return cursor.fetchall()


agent = guava.Agent(
    name="Taylor",
    organization="Peak Outdoors",
    purpose=(
        "to help Peak Outdoors customers check product availability and stock levels"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "product_availability_check",
        objective=(
            "A customer has called to check whether a specific product is in stock. "
            "Ask what they're looking for and search the product catalog."
        ),
        checklist=[
            guava.Say(
                "Thanks for calling Peak Outdoors. I'm Taylor. "
                "I can check stock availability for you right now. "
                "What product are you looking for?"
            ),
            guava.Field(
                key="product_query",
                field_type="text",
                description=(
                    "Ask for the product name or SKU they're interested in. "
                    "Capture exactly what they say."
                ),
                required=True,
            ),
        ],
    )


@agent.on_task_complete("product_availability_check")
def on_product_availability_check_done(call: guava.Call) -> None:
    query = (call.get_field("product_query") or "").strip()
    logging.info("Searching for product: %s", query)

    try:
        results = search_products(query)
    except Exception as e:
        logging.error("Database error searching for '%s': %s", query, e)
        results = []

    if not results:
        call.hangup(
            final_instructions=(
                f"Let the caller know you couldn't find any products matching '{query}'. "
                "Suggest they try a different name or SKU, or visit peakoutdoors.com "
                "to browse the full catalog."
            )
        )
        return

    product_lines = []
    for p in results:
        qty = int(p.get("stock_quantity") or 0)
        price = p.get("price")
        price_str = f"${float(price):,.2f}" if price else ""
        loc = p.get("location") or ""
        status = "in stock" if qty > 0 else "out of stock"
        line = f"{p['name']} (SKU: {p['sku']}): {status}"
        if qty > 0:
            line += f", {qty} available"
        if price_str:
            line += f", {price_str}"
        if loc:
            line += f", located in {loc}"
        product_lines.append(line)

    summary = "; ".join(product_lines)
    logging.info("Product search for '%s' returned %d result(s)", query, len(results))

    call.hangup(
        final_instructions=(
            f"Share the following stock information with the caller: {summary}. "
            "If an item is out of stock, let them know they can sign up for an in-stock alert "
            "at peakoutdoors.com or check back in a few days. "
            "If multiple items matched, mention them all."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
