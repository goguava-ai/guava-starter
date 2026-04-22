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


def create_warranty_claim(
    order_number: str,
    customer_name: str,
    customer_email: str,
    customer_phone: str,
    product_description: str,
    issue_description: str,
    purchase_date: str,
) -> str:
    """Inserts a warranty claim row and returns the generated claim number."""
    claim_number = "WC-" + secrets.token_hex(3).upper()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO warranty_claims
                    (claim_number, order_number, customer_name, customer_email,
                     customer_phone, product_description, issue_description,
                     purchase_date, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'open', NOW())
                """,
                (
                    claim_number,
                    order_number,
                    customer_name,
                    customer_email,
                    customer_phone,
                    product_description,
                    issue_description,
                    purchase_date,
                ),
            )
    return claim_number


class WarrantyClaimController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Peak Outdoors",
            agent_name="Morgan",
            agent_purpose=(
                "to help Peak Outdoors customers file warranty claims for defective products"
            ),
        )

        self.set_task(
            objective=(
                "A customer is calling to file a warranty claim for a product they purchased. "
                "Collect their contact information, the product details, and a description of the defect."
            ),
            checklist=[
                guava.Say(
                    "Thanks for calling Peak Outdoors. I'm Morgan. "
                    "I'm sorry to hear you're having an issue with your gear. "
                    "Let me get a warranty claim started for you."
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
                    description="Ask for their email address.",
                    required=True,
                ),
                guava.Field(
                    key="customer_phone",
                    field_type="text",
                    description="Ask for the best phone number to reach them.",
                    required=True,
                ),
                guava.Field(
                    key="order_number",
                    field_type="text",
                    description=(
                        "Ask for their order number if they have it (e.g. PO-10482). "
                        "Let them know it's okay if they don't."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="product_description",
                    field_type="text",
                    description="Ask them to describe the product — name, brand, and model if known.",
                    required=True,
                ),
                guava.Field(
                    key="purchase_date",
                    field_type="text",
                    description="Ask approximately when they purchased it.",
                    required=True,
                ),
                guava.Field(
                    key="issue_description",
                    field_type="text",
                    description=(
                        "Ask them to describe the defect or issue in their own words — "
                        "what happened, when it started, and how it affects the product."
                    ),
                    required=True,
                ),
            ],
            on_complete=self.file_warranty_claim,
        )

        self.accept_call()

    def file_warranty_claim(self):
        name = self.get_field("customer_name") or "Unknown"
        email = self.get_field("customer_email") or ""
        phone = self.get_field("customer_phone") or ""
        order_number = (self.get_field("order_number") or "").strip().upper()
        product = self.get_field("product_description") or "unknown product"
        purchase_date = self.get_field("purchase_date") or "unknown date"
        issue = self.get_field("issue_description") or "no description provided"

        logging.info("Filing warranty claim for %s — product: %s", name, product)

        try:
            claim_number = create_warranty_claim(
                order_number, name, email, phone, product, issue, purchase_date
            )
            logging.info("Warranty claim %s created for %s", claim_number, name)
            self.hangup(
                final_instructions=(
                    f"Let {name} know their warranty claim has been filed. "
                    f"Their claim number is {claim_number}. "
                    f"Product: {product}. Issue: {issue}. "
                    "A warranty specialist will review the claim and reach out by email "
                    "within 2–3 business days with next steps. "
                    "If the defect is covered, they'll receive either a replacement or store credit. "
                    "Thank them for their patience and for being a Peak Outdoors customer."
                )
            )
        except Exception as e:
            logging.error("Failed to file warranty claim for %s: %s", name, e)
            self.hangup(
                final_instructions=(
                    f"Apologize to {name} for a technical issue. "
                    "Ask them to email warranty@peakoutdoors.com with their product details "
                    "and a description of the issue, and assure them someone will respond "
                    "within one business day."
                )
            )


if __name__ == "__main__":
    logging_utils.configure_logging()
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=WarrantyClaimController,
    )
