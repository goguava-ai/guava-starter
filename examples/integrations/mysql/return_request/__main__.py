import guava
import os
import logging
from guava import logging_utils
import secrets
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


def get_order(order_number: str) -> dict | None:
    """Fetches an order by order number. Returns the order row or None."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, order_number, customer_email, status, created_at
                FROM orders
                WHERE order_number = %s
                LIMIT 1
                """,
                (order_number,),
            )
            return cursor.fetchone()


def create_return_request(
    order_number: str,
    customer_name: str,
    customer_email: str,
    item_description: str,
    return_reason: str,
    item_condition: str,
) -> str:
    """Creates a return request row and returns the generated RMA number."""
    rma_number = "RMA-" + secrets.token_hex(3).upper()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO return_requests
                    (rma_number, order_number, customer_name, customer_email,
                     item_description, return_reason, item_condition, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending', NOW())
                """,
                (
                    rma_number,
                    order_number,
                    customer_name,
                    customer_email,
                    item_description,
                    return_reason,
                    item_condition,
                ),
            )
    return rma_number


agent = guava.Agent(
    name="Casey",
    organization="Peak Outdoors",
    purpose=(
        "to help Peak Outdoors customers initiate returns and exchanges"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "return_request",
        objective=(
            "A customer has called to return an item. "
            "Verify their order, collect the return details, and create an RMA record."
        ),
        checklist=[
            guava.Say(
                "Thanks for calling Peak Outdoors. I'm Casey. "
                "I can get a return started for you right now. "
                "Do you have your order number handy?"
            ),
            guava.Field(
                key="order_number",
                field_type="text",
                description=(
                    "Ask for their order number. It typically starts with 'PO' followed "
                    "by digits (e.g. PO-10482). Capture it exactly as they say it."
                ),
                required=True,
            ),
            guava.Field(
                key="customer_name",
                field_type="text",
                description="Ask for their full name.",
                required=True,
            ),
            guava.Field(
                key="customer_email",
                field_type="text",
                description="Ask for their email address so we can send the return label.",
                required=True,
            ),
            guava.Field(
                key="item_description",
                field_type="text",
                description="Ask which item they're returning — name, size, color, or any details.",
                required=True,
            ),
            guava.Field(
                key="return_reason",
                field_type="multiple_choice",
                description="Ask why they're returning the item.",
                choices=[
                    "defective or damaged",
                    "wrong item received",
                    "doesn't fit",
                    "changed my mind",
                    "other",
                ],
                required=True,
            ),
            guava.Field(
                key="item_condition",
                field_type="multiple_choice",
                description="Ask about the condition of the item being returned.",
                choices=["unopened", "used once or twice", "used several times"],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("return_request")
def on_return_request_done(call: guava.Call) -> None:
    order_number = (call.get_field("order_number") or "").strip().upper()
    name = call.get_field("customer_name") or "Unknown"
    email = call.get_field("customer_email") or ""
    item = call.get_field("item_description") or "item"
    reason = call.get_field("return_reason") or "other"
    condition = call.get_field("item_condition") or "unknown"

    logging.info("Processing return for order %s — %s", order_number, name)

    try:
        order = get_order(order_number)
    except Exception as e:
        logging.error("DB error verifying order %s: %s", order_number, e)
        order = None

    if not order:
        call.hangup(
            final_instructions=(
                f"Let {name} know you couldn't find an order with number '{order_number}'. "
                "Ask them to double-check the number — it should start with 'PO'. "
                "Offer to transfer them to a team member if they need further help."
            )
        )
        return

    try:
        rma_number = create_return_request(
            order_number, name, email, item, reason, condition
        )
        logging.info("Return RMA %s created for order %s", rma_number, order_number)
        call.hangup(
            final_instructions=(
                f"Let {name} know their return has been approved. "
                f"Their RMA number is {rma_number}. "
                f"Item: {item}. Reason: {reason}. "
                "Let them know a prepaid return label will be emailed within 24 hours. "
                "They should pack the item securely and drop it off at any carrier location. "
                "Refunds are processed within 5–7 business days of receiving the item. "
                "Thank them for their patience."
            )
        )
    except Exception as e:
        logging.error("Failed to create return for %s: %s", name, e)
        call.hangup(
            final_instructions=(
                f"Apologize to {name} for a technical issue. "
                "Let them know a team member will follow up by email within one business day "
                "to complete the return process."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
