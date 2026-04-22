import guava
import os
import logging
from guava import logging_utils
import json
import requests
from datetime import datetime, timezone


agent = guava.Agent(
    name="Riley",
    organization="Summit Retail - Order Support",
    purpose=(
        "to assist customers calling about order status, resolve their inquiries, "
        "and ensure accurate records are kept in the contact system"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "save_results",
        objective=(
            "A customer has called Summit Retail about an order. Greet them warmly, "
            "collect their order details and inquiry, resolve or escalate as needed, "
            "and log the interaction."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Summit Retail Order Support. My name is Riley "
                "and I'm happy to help you with your order today."
            ),
            guava.Field(
                key="caller_name",
                description="Ask the caller for their full name.",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="order_number",
                description=(
                    "Ask the caller for their order number. It should start with 'ORD-' "
                    "followed by digits. If they don't have it, ask for the email "
                    "address used to place the order."
                ),
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="inquiry_type",
                description=(
                    "Ask what they need help with regarding their order. Categorize as: "
                    "shipping_status, return_exchange, missing_item, damaged_item, "
                    "cancellation, or other."
                ),
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="issue_details",
                description=(
                    "Ask the caller to describe their issue or question in detail. "
                    "Capture a clear summary."
                ),
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="resolution_provided",
                description=(
                    "Based on the inquiry, provide a resolution or next step. "
                    "Capture a summary of what was communicated to the customer."
                ),
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="satisfaction_rating",
                description=(
                    "Ask the customer to rate their experience on a scale of 1-5, "
                    "with 5 being excellent. Capture the rating."
                ),
                field_type="text",
                required=False,
            ),
        ],
    )


@agent.on_task_complete("save_results")
def on_done(call: guava.Call) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "Riley",
        "organization": "Summit Retail - Order Support",
        "use_case": "inbound_order_inquiry",
        "fields": {
            "caller_name": call.get_field("caller_name"),
            "order_number": call.get_field("order_number"),
            "inquiry_type": call.get_field("inquiry_type"),
            "issue_details": call.get_field("issue_details"),
            "resolution_provided": call.get_field("resolution_provided"),
            "satisfaction_rating": call.get_field("satisfaction_rating"),
        },
    }
    print(json.dumps(results, indent=2))
    logging.info("Order inquiry results saved locally.")

    # Push contact to RingCentral address book
    try:
        server_url = os.environ["RINGCENTRAL_SERVER_URL"]
        token = os.environ["RINGCENTRAL_ACCESS_TOKEN"]
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        contact_payload = {
            "firstName": call.get_field("caller_name"),
            "notes": json.dumps({
                "order_number": call.get_field("order_number"),
                "inquiry_type": call.get_field("inquiry_type"),
                "issue_details": call.get_field("issue_details"),
                "resolution_provided": call.get_field("resolution_provided"),
                "satisfaction_rating": call.get_field("satisfaction_rating"),
                "call_timestamp": datetime.now(timezone.utc).isoformat(),
                "source": "guava_voice_agent",
            }),
        }
        resp = requests.post(
            f"{server_url}/restapi/v1.0/account/~/extension/~/address-book/contact",
            headers=headers,
            json=contact_payload,
            timeout=10,
        )
        resp.raise_for_status()
        logging.info("RingCentral contact created successfully.")
    except Exception as e:
        logging.error("Failed to push to RingCentral: %s", e)

    call.hangup(
        final_instructions=(
            "Thank the customer for calling Summit Retail. Summarize the resolution "
            "or next steps for their order inquiry. Let them know they can call back "
            "anytime if they need further assistance. Wish them a great day."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
