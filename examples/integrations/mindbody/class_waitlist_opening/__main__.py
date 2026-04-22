import guava
import os
import logging
from guava import logging_utils
import argparse
import requests


BASE_URL = "https://api.mindbodyonline.com/public/v6"
API_KEY = os.environ["MINDBODY_API_KEY"]
SITE_ID = os.environ["MINDBODY_SITE_ID"]
STAFF_TOKEN = os.environ["MINDBODY_STAFF_TOKEN"]

HEADERS = {
    "API-Key": API_KEY,
    "SiteId": SITE_ID,
    "Authorization": f"Bearer {STAFF_TOKEN}",
    "Content-Type": "application/json",
}


def fetch_class_details(class_id: int) -> dict:
    """Return details for a specific class to verify it still has an open spot."""
    resp = requests.get(
        f"{BASE_URL}/class/classes",
        headers=HEADERS,
        params={"classIds": class_id},
        timeout=10,
    )
    resp.raise_for_status()
    classes = resp.json().get("Classes", [])
    return classes[0] if classes else {}


def add_client_to_class(client_id: str, class_id: int) -> dict:
    """Enroll the client in the class, removing them from the waitlist."""
    payload = {
        "ClientId": client_id,
        "ClassId": class_id,
        "SendEmail": True,
        "RequirePayment": False,
        "Waitlist": False,
    }
    resp = requests.post(
        f"{BASE_URL}/class/addclienttoclass",
        headers=HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("Class", {})


def remove_client_from_waitlist(client_id: str, class_id: int) -> dict:
    """Remove the client from the class waitlist if they decline the spot."""
    payload = {
        "ClientId": client_id,
        "ClassId": class_id,
        "RemoveFromWaitlist": True,
    }
    resp = requests.post(
        f"{BASE_URL}/class/removeClientFromClass",
        headers=HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


agent = guava.Agent(
    name="Riley",
    organization="Harmony Wellness Center",
    purpose="to notify waitlisted clients about open class spots",
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    client_name = call.get_variable("client_name")
    client_id = call.get_variable("client_id")
    class_id = int(call.get_variable("class_id"))

    # Verify the spot is still open before dialing.
    spot_still_available = False
    try:
        class_details = fetch_class_details(class_id)
        total_booked = class_details.get("TotalBooked", 0)
        max_capacity = class_details.get("MaxCapacity", 0)
        spot_still_available = (
            max_capacity > 0 and total_booked < max_capacity
        )
        logging.info(
            "Class %s capacity check: %d/%d booked — spot available: %s",
            class_id, total_booked, max_capacity, spot_still_available,
        )
    except Exception as e:
        logging.error("Failed to check class capacity for class %s: %s", class_id, e)
        # Proceed optimistically; let the enrollment call surface the error if needed.
        spot_still_available = True

    call.set_variable("spot_still_available", spot_still_available)
    call.reach_person(contact_full_name=client_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    client_name = call.get_variable("client_name")
    class_name = call.get_variable("class_name")
    class_datetime = call.get_variable("class_datetime")
    instructor_name = call.get_variable("instructor_name")

    if outcome == "unavailable":
        call.hangup(
            final_instructions=(
                f"Leave an urgent but friendly voicemail for {client_name} letting them know "
                f"a spot has opened in the {class_name} class on {class_datetime} "
                f"with {instructor_name} at Harmony Wellness Center. "
                "Ask them to call back or book through the app as soon as possible, "
                "as spots fill up quickly. Keep it under 25 seconds and be upbeat."
            )
        )
    elif outcome == "available":
        spot_still_available = call.get_variable("spot_still_available")

        if not spot_still_available:
            # Spot was taken between the pre-check and the call connecting — inform client gracefully.
            call.hangup(
                final_instructions=(
                    f"Apologize to {client_name} and let them know the spot in the "
                    f"{class_name} class unfortunately just filled up before we could connect. "
                    "Let them know they are still on the waitlist and we will call again if another "
                    "spot opens. Thank them for their patience. Be warm and apologetic."
                )
            )
            return

        call.set_task(
            "collect_spot_decision",
            objective=(
                f"Notify {client_name} that a spot has opened in the "
                f"{class_name} class on {class_datetime} and confirm whether "
                "they want to take the spot."
            ),
            checklist=[
                guava.Say(
                    f"Hi {client_name}! This is Riley calling from Harmony Wellness Center "
                    f"with great news — a spot just opened up in the {class_name} class "
                    f"with {instructor_name} on {class_datetime}! "
                    "You were on the waitlist and we wanted to reach you right away."
                ),
                guava.Field(
                    key="wants_spot",
                    field_type="multiple_choice",
                    description=(
                        f"Ask {client_name} if they would like to take the open spot in the class. "
                        "Let them know spots go quickly so we want to confirm right now."
                    ),
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="payment_method",
                    field_type="multiple_choice",
                    description=(
                        "If they said yes, ask how they would like to pay — using an existing class pack "
                        "or credit on their account, or they can pay at the studio. "
                        "Only ask this if they said yes."
                    ),
                    choices=["use existing credits", "pay at studio"],
                    required=False,
                ),
                guava.Field(
                    key="decline_reason",
                    field_type="text",
                    description=(
                        "If they said no, ask briefly whether they would like to stay on the waitlist "
                        "for future openings or be removed. This helps us keep our list current."
                    ),
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("collect_spot_decision")
def handle_outcome(call: guava.Call) -> None:
    client_name = call.get_variable("client_name")
    client_id = call.get_variable("client_id")
    class_id = int(call.get_variable("class_id"))
    class_name = call.get_variable("class_name")
    class_datetime = call.get_variable("class_datetime")
    instructor_name = call.get_variable("instructor_name")
    wants_spot = call.get_field("wants_spot")
    decline_reason = call.get_field("decline_reason")

    if wants_spot == "yes":
        enrolled = False
        try:
            add_client_to_class(client_id, class_id)
            enrolled = True
            logging.info(
                "Enrolled client %s in class %s (%s)",
                client_id, class_id, class_name,
            )
        except Exception as e:
            logging.error(
                "Failed to enroll client %s in class %s: %s",
                client_id, class_id, e,
            )

        if enrolled:
            call.hangup(
                final_instructions=(
                    f"Congratulate {client_name} — they are officially booked in the "
                    f"{class_name} class on {class_datetime} with {instructor_name}! "
                    "Let them know a confirmation email is on its way. Remind them to arrive a few "
                    "minutes early and bring water and a mat if needed. Be enthusiastic and encouraging."
                )
            )
        else:
            call.hangup(
                final_instructions=(
                    f"Apologize to {client_name} — unfortunately there was a technical issue "
                    "while trying to secure their spot. Ask them to call the studio directly or "
                    "log in to the app to complete the enrollment. Thank them for their understanding. "
                    "Be apologetic and helpful."
                )
            )

    else:
        # Client declined — ask about staying on waitlist (captured in decline_reason).
        # Remove from waitlist only if they explicitly asked to be removed.
        if decline_reason and "remove" in decline_reason.lower():
            try:
                remove_client_from_waitlist(client_id, class_id)
                logging.info(
                    "Removed client %s from waitlist for class %s",
                    client_id, class_id,
                )
            except Exception as e:
                logging.error(
                    "Failed to remove client %s from waitlist for class %s: %s",
                    client_id, class_id, e,
                )

            call.hangup(
                final_instructions=(
                    f"Thank {client_name} and confirm they have been removed from the waitlist "
                    f"for the {class_name} class. Let them know they can always re-join the "
                    "waitlist through the app or by calling the studio. Wish them well and be warm."
                )
            )
        else:
            call.hangup(
                final_instructions=(
                    f"Thank {client_name} for letting us know. Confirm they are staying on the "
                    f"waitlist for future {class_name} openings and we'll call them if another "
                    "spot comes up. Wish them a great day. Be warm and brief."
                )
            )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Notify a waitlisted client that a spot has opened in a class."
    )
    parser.add_argument("phone", help="Client phone number in E.164 format, e.g. +14155550178")
    parser.add_argument("--client-id", required=True, help="Mindbody client ID")
    parser.add_argument("--name", required=True, help="Client full name")
    parser.add_argument("--class-id", required=True, type=int, help="Mindbody class ID")
    parser.add_argument(
        "--class-name",
        required=True,
        help="Class name, e.g. 'Saturday Morning Yoga Flow'",
    )
    parser.add_argument(
        "--class-datetime",
        required=True,
        help="Human-readable class date and time, e.g. 'Saturday at 9:00 AM'",
    )
    parser.add_argument(
        "--instructor-name",
        required=True,
        help="Instructor name, e.g. 'Instructor Priya'",
    )
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "client_name": args.name,
            "client_id": args.client_id,
            "class_id": str(args.class_id),
            "class_name": args.class_name,
            "class_datetime": args.class_datetime,
            "instructor_name": args.instructor_name,
        },
    )
