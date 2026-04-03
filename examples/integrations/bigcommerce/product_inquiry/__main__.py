import guava
import os
import logging
import json
import requests
from datetime import datetime

logging.basicConfig(level=logging.INFO)

STORE_HASH = os.environ["BIGCOMMERCE_STORE_HASH"]
AUTH_TOKEN = os.environ["BIGCOMMERCE_AUTH_TOKEN"]
V3_BASE = f"https://api.bigcommerce.com/stores/{STORE_HASH}/v3"

HEADERS = {
    "X-Auth-Token": AUTH_TOKEN,
    "Content-Type": "application/json",
    "Accept": "application/json",
}


def _availability_label(product: dict) -> str:
    """Map BigCommerce availability and inventory_level to a customer-friendly phrase."""
    availability = product.get("availability", "available")
    inventory_level = product.get("inventory_level", 0)
    inventory_tracking = product.get("inventory_tracking", "none")

    if availability == "preorder":
        return "available for pre-order"
    if availability == "disabled":
        return "currently unavailable"
    # availability == "available"
    if inventory_tracking == "none":
        # No inventory tracking — assume in stock
        return "in stock"
    if inventory_level > 0:
        return f"in stock ({inventory_level} available)"
    return "out of stock"


class ProductInquiryController(guava.CallController):
    def __init__(self):
        super().__init__()
        self.product = None

        self.set_persona(
            organization_name="Harbor House",
            agent_name="Casey",
            agent_purpose="to help Harbor House customers find the right products and get answers about availability, pricing, and product details",
        )

        self.set_task(
            objective=(
                "A customer has called Harbor House with a question about a product. "
                "Greet them, find out which product they're asking about, and understand "
                "what they want to know so you can look it up."
            ),
            checklist=[
                guava.Say(
                    "Thanks for calling Harbor House! This is Casey. I'd be happy to help "
                    "you with any product questions today."
                ),
                guava.Field(
                    key="product_name",
                    description="Ask what product they're looking for.",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="inquiry_type",
                    description=(
                        "Ask what they'd like to know about the product. "
                        "Offer these options: 'check if it's in stock', 'get the price', "
                        "'learn more about the product', "
                        "'check if it comes in different sizes or colors'."
                    ),
                    field_type="multiple_choice",
                    choices=[
                        "check if it's in stock",
                        "get the price",
                        "learn more about the product",
                        "check if it comes in different sizes or colors",
                    ],
                    required=True,
                ),
            ],
            on_complete=self.search_product,
        )

        self.accept_call()

    def search_product(self):
        product_name = self.get_field("product_name")
        inquiry_type = self.get_field("inquiry_type")

        try:
            resp = requests.get(
                f"{V3_BASE}/catalog/products",
                headers=HEADERS,
                params={"name": product_name, "include": "variants", "limit": 5},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json().get("data", [])
        except Exception as e:
            logging.error("Failed to search products for '%s': %s", product_name, e)
            self.hangup(
                final_instructions=(
                    "Apologize to the customer and let them know we were unable to retrieve "
                    "product information right now. Ask them to visit harborhouse.com to browse "
                    "the full catalog, or call back shortly. Thank them for their patience."
                )
            )
            return

        if not data:
            self.hangup(
                final_instructions=(
                    f"Let the customer know that we couldn't find a product matching "
                    f"'{product_name}' in our catalog. Suggest they visit harborhouse.com "
                    "to search the full product range, or offer to transfer them "
                    "to someone who can help further. Thank them for calling Harbor House."
                )
            )
            return

        # Use the best-matching result (first returned)
        product = data[0]
        self.product = product

        product_full_name = product.get("name", product_name)
        price = product.get("price", "")
        availability_label = _availability_label(product)
        description = product.get("description", "")
        variants = product.get("variants", {}).get("data", []) if isinstance(product.get("variants"), dict) else []

        # Strip HTML tags from description for voice
        import re
        clean_description = re.sub(r"<[^>]+>", " ", description).strip()
        clean_description = re.sub(r"\s+", " ", clean_description)
        short_description = clean_description[:300] + "..." if len(clean_description) > 300 else clean_description

        # Build variant summary for sizes/colors
        variant_summary = ""
        if variants:
            option_values = []
            for v in variants[:10]:
                for opt in v.get("option_values", []):
                    label = opt.get("label", "")
                    if label and label not in option_values:
                        option_values.append(label)
            if option_values:
                variant_summary = ", ".join(option_values[:8])

        print(json.dumps({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "product_id": product.get("id"),
            "product_name": product_full_name,
            "price": price,
            "availability": availability_label,
            "inquiry_type": inquiry_type,
            "variant_count": len(variants),
        }, indent=2))
        logging.info("Product found: %s (id=%s)", product_full_name, product.get("id"))

        # Build what to say based on inquiry type
        inquiry_lower = inquiry_type.lower()

        if "in stock" in inquiry_lower:
            detail_line = f"That product is currently {availability_label}."
        elif "price" in inquiry_lower:
            detail_line = f"The price for {product_full_name} is ${price}." if price else f"I wasn't able to retrieve a price for {product_full_name} right now."
        elif "learn more" in inquiry_lower:
            detail_line = (
                f"Here are some details about {product_full_name}: {short_description}"
                if short_description
                else f"Unfortunately I don't have additional details for {product_full_name} on hand right now."
            )
        elif "sizes or colors" in inquiry_lower:
            if variant_summary:
                detail_line = f"{product_full_name} is available in the following options: {variant_summary}."
            else:
                detail_line = f"{product_full_name} does not appear to have multiple variants listed in our system."
        else:
            detail_line = f"{product_full_name} is {availability_label} and priced at ${price}."

        self.set_task(
            objective=(
                f"You've looked up '{product_full_name}' for the customer. "
                "Share the relevant information and ask if they'd like to place an order."
            ),
            checklist=[
                guava.Say(
                    f"I found it! {detail_line} "
                    f"The current price is ${price} and it's {availability_label}."
                    if "price" not in inquiry_lower and "in stock" not in inquiry_lower
                    else f"I found it! {detail_line}"
                ),
                guava.Field(
                    key="next_action",
                    description=(
                        "Ask the customer if they'd like to order, are just browsing, or "
                        "would like to be transferred to someone for more help. "
                        "Capture one of: 'yes, I'd like to order', 'no, just browsing', 'transfer to someone'."
                    ),
                    field_type="multiple_choice",
                    choices=["yes, I'd like to order", "no, just browsing", "transfer to someone"],
                    required=True,
                ),
            ],
            on_complete=self.route_next_action,
        )

    def route_next_action(self):
        action = self.get_field("next_action")
        product_full_name = self.product.get("name", "the item") if self.product else "the item"
        label = (action or "").strip().lower()

        if "order" in label:
            self.hangup(
                final_instructions=(
                    f"Let the customer know they can place an order for {product_full_name} "
                    "by visiting harborhouse.com and adding it to their cart, or offer to transfer "
                    "them to the sales team to complete the order by phone. "
                    "Let them know their cart will be saved if they visit the site. "
                    "Thank them for calling Harbor House."
                )
            )
        elif "transfer" in label:
            self.hangup(
                final_instructions=(
                    "Let the customer know you are transferring them to a Harbor House product "
                    "specialist who can answer any additional questions and assist with placing an order. "
                    "Thank them for their patience."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    "Thank the customer for calling Harbor House. Let them know they're always "
                    "welcome to browse the full catalog at harborhouse.com and call back any time "
                    "with questions. Wish them a great day."
                )
            )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=ProductInquiryController,
    )
