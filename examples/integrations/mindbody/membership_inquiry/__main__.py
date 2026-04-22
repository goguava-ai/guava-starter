import guava
import os
import logging
from guava import logging_utils
import json
import requests
from datetime import datetime, timezone


BASE_URL = "https://api.mindbodyonline.com/public/v6"
API_KEY = os.environ["MINDBODY_API_KEY"]
SITE_ID = os.environ["MINDBODY_SITE_ID"]


def get_headers(user_token: str | None = None) -> dict:
    headers = {
        "Api-Key": API_KEY,
        "SiteId": SITE_ID,
        "Content-Type": "application/json",
    }
    if user_token:
        headers["Authorization"] = f"Bearer {user_token}"
    return headers


def get_staff_token() -> str:
    """Obtain a staff user token for API operations that require authentication."""
    resp = requests.post(
        f"{BASE_URL}/usertoken/issue",
        headers={"Api-Key": API_KEY, "SiteId": SITE_ID, "Content-Type": "application/json"},
        json={
            "Username": os.environ["MINDBODY_STAFF_USERNAME"],
            "Password": os.environ["MINDBODY_STAFF_PASSWORD"],
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["AccessToken"]


def format_expiration(iso_date: str | None) -> str:
    """Convert an ISO date string to a human-readable format."""
    if not iso_date:
        return "no expiration"
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        return dt.strftime("%B %-d, %Y")
    except (ValueError, AttributeError):
        return iso_date


agent = guava.Agent(
    name="Casey",
    organization="FlexFit Studio",
    purpose="to help FlexFit Studio members understand their membership status and remaining class credits",
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "collect_phone",
        objective=(
            "A FlexFit Studio member has called to ask about their membership and class credits. "
            "Greet them, collect their phone number to look up their account, and then read back "
            "a clear summary of their active memberships and class packs."
        ),
        checklist=[
            guava.Say(
                "Thanks for calling FlexFit Studio! I'm Casey. I'd be happy to pull up your "
                "membership details — let me grab your account."
            ),
            guava.Field(
                key="phone",
                field_type="text",
                description=(
                    "Ask for the phone number they have on file with FlexFit Studio. "
                    "Capture it exactly as they say it."
                ),
                required=True,
            ),
        ],
    )


@agent.on_task_complete("collect_phone")
def lookup_client(call: guava.Call) -> None:
    phone = call.get_field("phone")
    logging.info("Looking up Mindbody client by phone: %s", phone)

    try:
        token = get_staff_token()
        resp = requests.get(
            f"{BASE_URL}/client/clients",
            headers=get_headers(token),
            params={"SearchText": phone},
            timeout=10,
        )
        resp.raise_for_status()
        clients = resp.json().get("Clients", [])

        if not clients:
            logging.warning("No Mindbody client found for phone: %s", phone)
            call.hangup(
                final_instructions=(
                    "Let the caller know we couldn't find an account matching that phone number. "
                    "Ask them to double-check the number on file, or stop by the front desk for "
                    "assistance. Thank them for calling FlexFit Studio."
                )
            )
            return

        client = clients[0]
        client_id = str(client.get("Id", ""))
        first_name = client.get("FirstName", "")
        last_name = client.get("LastName", "")
        client_name = f"{first_name} {last_name}".strip() or "there"
        logging.info("Found client: %s (ID: %s)", client_name, client_id)

    except Exception as e:
        logging.error("Failed to look up Mindbody client: %s", e)
        call.hangup(
            final_instructions=(
                "Apologize and let the caller know we're having trouble accessing the member "
                "database right now. Ask them to try again shortly."
            )
        )
        return

    call.client_id = client_id
    call.client_name = client_name

    # Fetch the member's active services (memberships and class packs).
    active_services = []
    try:
        token = get_staff_token()
        resp = requests.get(
            f"{BASE_URL}/client/clientservices",
            headers=get_headers(token),
            params={"ClientID": client_id},
            timeout=10,
        )
        resp.raise_for_status()
        all_services = resp.json().get("ClientServices", [])

        # Filter to currently active services only.
        active_services = [s for s in all_services if s.get("Current")]
        logging.info(
            "Fetched %d active service(s) for client %s.",
            len(active_services), client_id,
        )

    except Exception as e:
        logging.error("Failed to fetch client services: %s", e)
        active_services = []

    call.active_services = active_services

    # Build a spoken membership summary and present it to the member.
    if not active_services:
        summary_say = (
            f"I've pulled up your account, {client_name}. It looks like you don't have "
            "any active memberships or class packs on file right now."
        )
    else:
        lines = []
        for svc in active_services:
            name = svc.get("Name", "Unknown service")
            count = svc.get("Count")
            expiration = format_expiration(svc.get("ExpirationDate"))

            if count is not None:
                lines.append(f"{name}: {count} class{'es' if count != 1 else ''} remaining, expires {expiration}")
            else:
                lines.append(f"{name}: active, expires {expiration}")

        services_text = "; ".join(lines)
        summary_say = (
            f"I've pulled up your account, {client_name}. Here's what's active: "
            f"{services_text}."
        )

    call.set_task(
        "handle_next_action",
        objective=(
            f"Read the membership summary to {client_name} and find out what else "
            "they need help with."
        ),
        checklist=[
            guava.Say(summary_say),
            guava.Field(
                key="next_action",
                field_type="multiple_choice",
                description=(
                    "Ask what else the member would like help with today. "
                    "Map their answer to the closest option."
                ),
                choices=[
                    "book a class",
                    "cancel a booking",
                    "purchase more classes",
                    "nothing, all good",
                ],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("handle_next_action")
def route_next_action(call: guava.Call) -> None:
    action = call.get_field("next_action")
    client_id = call.client_id
    client_name = call.client_name
    active_services = call.active_services

    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "Casey",
        "organization": "FlexFit Studio",
        "use_case": "membership_inquiry",
        "client_id": client_id,
        "client_name": client_name,
        "active_services": [
            {
                "name": s.get("Name"),
                "count": s.get("Count"),
                "expiration": s.get("ExpirationDate"),
            }
            for s in active_services
        ],
        "fields": {
            "phone": call.get_field("phone"),
            "next_action": action,
        },
    }
    print(json.dumps(results, indent=2))
    logging.info("Membership inquiry result saved.")

    if action == "book a class":
        call.hangup(
            final_instructions=(
                f"Let {client_name} know they can book a class quickly online at "
                "flexfitstudio.com, or call back anytime and we'll be happy to book one over "
                "the phone. Encourage them to grab a spot before classes fill up. "
                "Thank them for calling FlexFit Studio!"
            )
        )

    elif action == "cancel a booking":
        call.hangup(
            final_instructions=(
                f"Let {client_name} know they can call back at any time to cancel a "
                "specific class or appointment — just have the class name or date handy so we "
                "can pull it up quickly. Thank them for calling FlexFit Studio!"
            )
        )

    elif action == "purchase more classes":
        call.hangup(
            final_instructions=(
                f"Let {client_name} know you're going to transfer them to the front desk "
                "right now so they can purchase a class pack or membership. Thank them for "
                "calling FlexFit Studio and let them know someone will be right with them."
            )
        )

    else:
        # "nothing, all good"
        call.hangup(
            final_instructions=(
                f"Wish {client_name} a wonderful day. Let them know FlexFit Studio is "
                "always here if they need anything, and we look forward to seeing them in class. "
                "Thank them for calling!"
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
