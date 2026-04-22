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

# Cancellations within this many hours of class start trigger the late-cancel warning.
LATE_CANCEL_WINDOW_HOURS = 12


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


agent = guava.Agent(
    name="Sam",
    organization="FlexFit Studio",
    purpose="to help FlexFit Studio members manage and cancel their class bookings and appointments",
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "collect_cancellation_request",
        objective=(
            "A FlexFit Studio member has called to cancel a class booking or appointment. "
            "Greet them, collect their phone number to locate their account, and find out "
            "what they'd like to cancel."
        ),
        checklist=[
            guava.Say(
                "Thanks for calling FlexFit Studio! This is Sam. I can help you with a "
                "cancellation today — let me pull up your account."
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
            guava.Field(
                key="cancel_type",
                field_type="multiple_choice",
                description=(
                    "Ask what they'd like to cancel. Map their answer to the closest option."
                ),
                choices=["a class booking", "a personal training session", "a spa appointment"],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("collect_cancellation_request")
def lookup_client(call: guava.Call) -> None:
    phone = call.get_field("phone")
    cancel_type = call.get_field("cancel_type")

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
                    "Ask them to double-check the number on file, or reach out to the front desk "
                    "for help. Thank them for calling FlexFit Studio."
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
                "Apologize and let them know we're having trouble reaching the member database "
                "right now. Ask them to try again shortly or stop by the front desk."
            )
        )
        return

    call.set_variable("client_id", client_id)
    call.set_variable("client_name", client_name)

    # Route to the appropriate cancellation flow based on type.
    if cancel_type == "a class booking":
        _fetch_and_present_class(call, client_id, client_name)
    else:
        # For personal training or spa, fetch upcoming appointments.
        _fetch_and_present_appointment(call, client_id, client_name, cancel_type)


def _fetch_and_present_class(call: guava.Call, client_id: str, client_name: str) -> None:
    """Fetch the member's most upcoming class visit so we can offer to cancel it."""
    today_str = datetime.now().date().isoformat()

    try:
        token = get_staff_token()
        resp = requests.get(
            f"{BASE_URL}/client/clientvisits",
            headers=get_headers(token),
            params={
                "ClientID": client_id,
                "StartDate": today_str,
            },
            timeout=10,
        )
        resp.raise_for_status()
        visits = resp.json().get("Visits", [])

        # Sort ascending by start time and take the soonest.
        upcoming = sorted(
            [v for v in visits if v.get("StartDateTime")],
            key=lambda v: v["StartDateTime"],
        )

        if not upcoming:
            logging.info("No upcoming class visits found for client %s.", client_id)
            call.hangup(
                final_instructions=(
                    f"Let {client_name} know we couldn't find any upcoming class bookings "
                    "on their account. If they think there's a mistake, suggest they visit the "
                    "front desk or check their schedule online. Thank them for calling FlexFit Studio."
                )
            )
            return

        upcoming_visit = upcoming[0]
        class_name = upcoming_visit.get("Name", "your class")
        start_raw = upcoming_visit.get("StartDateTime", "")

        is_late_cancel = False
        try:
            dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
            display_time = dt.strftime("%A, %B %-d at %-I:%M %p")
            # Determine if this is a late cancellation.
            now_utc = datetime.now(timezone.utc)
            hours_until = (dt.astimezone(timezone.utc) - now_utc).total_seconds() / 3600
            is_late_cancel = hours_until < LATE_CANCEL_WINDOW_HOURS
        except (ValueError, AttributeError):
            display_time = start_raw
            is_late_cancel = False

        logging.info(
            "Most upcoming visit: %s on %s. Late cancel: %s",
            class_name, display_time, is_late_cancel,
        )

    except Exception as e:
        logging.error("Failed to fetch client visits: %s", e)
        call.hangup(
            final_instructions=(
                "Apologize and let the caller know we're having trouble loading their schedule. "
                "Ask them to try again shortly or contact the front desk."
            )
        )
        return

    call.set_variable("upcoming_visit", upcoming_visit)
    call.set_variable("is_late_cancel", is_late_cancel)

    # Build the late-cancel warning if needed, then ask for confirmation.
    class_name = upcoming_visit.get("Name", "your class")
    start_raw = upcoming_visit.get("StartDateTime", "")
    try:
        dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
        display_time = dt.strftime("%A, %B %-d at %-I:%M %p")
    except (ValueError, AttributeError):
        display_time = start_raw

    late_cancel_note = (
        " Please note that because this class starts in less than 12 hours, this will be "
        "recorded as a late cancellation, which may result in a fee or forfeiture of the "
        "class credit per our studio policy."
        if is_late_cancel else ""
    )

    call.set_task(
        "confirm_class_cancel",
        objective=(
            f"Confirm with {client_name} which class to cancel and get their final decision."
        ),
        checklist=[
            guava.Say(
                f"I found your upcoming booking: {class_name} on {display_time}."
                f"{late_cancel_note} Would you like to cancel this class?"
            ),
            guava.Field(
                key="confirm_cancel",
                field_type="multiple_choice",
                description=(
                    "Ask the member to confirm whether they want to go ahead with the cancellation. "
                    "Map their answer to 'yes, cancel it' or 'no, keep it'."
                ),
                choices=["yes, cancel it", "no, keep it"],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("confirm_class_cancel")
def execute_class_cancellation(call: guava.Call) -> None:
    confirm = call.get_field("confirm_cancel")
    client_id = call.get_variable("client_id")
    client_name = call.get_variable("client_name")
    upcoming_visit = call.get_variable("upcoming_visit")
    is_late_cancel = call.get_variable("is_late_cancel")

    class_name = upcoming_visit.get("Name", "your class")
    start_raw = upcoming_visit.get("StartDateTime", "")
    class_id = upcoming_visit.get("ClassId")

    try:
        dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
        display_time = dt.strftime("%A, %B %-d at %-I:%M %p")
    except (ValueError, AttributeError):
        display_time = start_raw

    if confirm != "yes, cancel it":
        call.hangup(
            final_instructions=(
                f"Let {client_name} know their {class_name} booking on {display_time} "
                "has been kept — no changes were made. Thank them for calling FlexFit Studio "
                "and wish them a great workout!"
            )
        )
        return

    try:
        token = get_staff_token()
        resp = requests.post(
            f"{BASE_URL}/class/removeclientfromclass",
            headers=get_headers(token),
            json={
                "ClientId": client_id,
                "ClassId": class_id,
                "SendEmail": False,
                "LateCancel": is_late_cancel,
            },
            timeout=10,
        )
        resp.raise_for_status()
        logging.info(
            "Removed client %s from class %s. Late cancel: %s",
            client_id, class_id, is_late_cancel,
        )
    except Exception as e:
        logging.error("Failed to remove client from class: %s", e)
        call.hangup(
            final_instructions=(
                f"Apologize to {client_name} — we ran into a problem processing the "
                "cancellation. Please ask them to try again or contact the front desk directly."
            )
        )
        return

    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "Sam",
        "organization": "FlexFit Studio",
        "use_case": "appointment_cancellation",
        "client_id": client_id,
        "client_name": client_name,
        "class_id": class_id,
        "class_name": class_name,
        "class_start": start_raw,
        "late_cancel": is_late_cancel,
        "fields": {
            "phone": call.get_field("phone"),
            "cancel_type": call.get_field("cancel_type"),
            "confirm_cancel": confirm,
        },
    }
    print(json.dumps(results, indent=2))
    logging.info("Cancellation result saved.")

    late_note = (
        " As mentioned, this will be marked as a late cancellation."
        if is_late_cancel else ""
    )
    call.hangup(
        final_instructions=(
            f"Confirm to {client_name} that their {class_name} class on {display_time} "
            f"has been successfully cancelled.{late_note} Let them know we'd love to see them "
            "at another class soon. Thank them for calling FlexFit Studio."
        )
    )


def _fetch_and_present_appointment(call: guava.Call, client_id: str, client_name: str, cancel_type: str) -> None:
    """Fetch the member's most upcoming personal training or spa appointment."""
    today_str = datetime.now().date().isoformat()

    try:
        token = get_staff_token()
        resp = requests.get(
            f"{BASE_URL}/appointment/staffappointments",
            headers=get_headers(token),
            params={
                "ClientId": client_id,
                "StartDate": today_str,
            },
            timeout=10,
        )
        resp.raise_for_status()
        appointments = resp.json().get("Appointments", [])

        upcoming = sorted(
            [a for a in appointments if a.get("StartDateTime")],
            key=lambda a: a["StartDateTime"],
        )

        if not upcoming:
            logging.info("No upcoming appointments found for client %s.", client_id)
            call.hangup(
                final_instructions=(
                    f"Let {client_name} know we couldn't find any upcoming {cancel_type} "
                    "bookings on their account. If they believe there's a mistake, ask them to "
                    "contact the front desk. Thank them for calling FlexFit Studio."
                )
            )
            return

        appt = upcoming[0]
        appt_id = appt.get("Id")
        staff_name = appt.get("Staff", {}).get("Name", "your trainer")
        start_raw = appt.get("StartDateTime", "")

        is_late_cancel = False
        try:
            dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
            display_time = dt.strftime("%A, %B %-d at %-I:%M %p")
            now_utc = datetime.now(timezone.utc)
            hours_until = (dt.astimezone(timezone.utc) - now_utc).total_seconds() / 3600
            is_late_cancel = hours_until < LATE_CANCEL_WINDOW_HOURS
        except (ValueError, AttributeError):
            display_time = start_raw
            is_late_cancel = False

        logging.info(
            "Most upcoming appointment: ID %s on %s with %s. Late cancel: %s",
            appt_id, display_time, staff_name, is_late_cancel,
        )

        call.set_variable("pending_appt_id", appt_id)
        call.set_variable("pending_appt_display", display_time)
        call.set_variable("pending_start_raw", start_raw)
        call.set_variable("is_late_cancel", is_late_cancel)

    except Exception as e:
        logging.error("Failed to fetch appointments: %s", e)
        call.hangup(
            final_instructions=(
                "Apologize and let the caller know we're having trouble loading their appointments. "
                "Please ask them to contact the front desk for assistance."
            )
        )
        return

    late_cancel_note = (
        " Please be aware that since this appointment is within 12 hours, it will be marked "
        "as a late cancellation and a fee may apply per our studio policy."
        if is_late_cancel else ""
    )

    call.set_task(
        "confirm_appointment_cancel",
        objective=(
            f"Confirm with {client_name} which appointment to cancel and get their decision."
        ),
        checklist=[
            guava.Say(
                f"I found your upcoming {cancel_type} on {display_time} "
                f"with {staff_name}.{late_cancel_note} "
                "Would you like to cancel this appointment?"
            ),
            guava.Field(
                key="confirm_cancel",
                field_type="multiple_choice",
                description=(
                    "Ask whether they want to proceed with the cancellation. "
                    "Map to 'yes, cancel it' or 'no, keep it'."
                ),
                choices=["yes, cancel it", "no, keep it"],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("confirm_appointment_cancel")
def execute_appointment_cancellation(call: guava.Call) -> None:
    confirm = call.get_field("confirm_cancel")
    cancel_type = call.get_field("cancel_type")
    client_id = call.get_variable("client_id")
    client_name = call.get_variable("client_name")
    appt_id = call.get_variable("pending_appt_id")
    display_time = call.get_variable("pending_appt_display")
    start_raw = call.get_variable("pending_start_raw")
    is_late_cancel = call.get_variable("is_late_cancel")

    if confirm != "yes, cancel it":
        call.hangup(
            final_instructions=(
                f"Let {client_name} know their {cancel_type} on {display_time} "
                "has been kept — no changes made. Thank them for calling FlexFit Studio."
            )
        )
        return

    try:
        token = get_staff_token()
        resp = requests.delete(
            f"{BASE_URL}/appointment/cancelappointment",
            headers=get_headers(token),
            params={"AppointmentId": appt_id},
            timeout=10,
        )
        resp.raise_for_status()
        logging.info(
            "Cancelled appointment %s for client %s. Late cancel: %s",
            appt_id, client_id, is_late_cancel,
        )
    except Exception as e:
        logging.error("Failed to cancel appointment %s: %s", appt_id, e)
        call.hangup(
            final_instructions=(
                f"Apologize to {client_name} — we couldn't complete the cancellation right now. "
                "Please ask them to contact the front desk for assistance."
            )
        )
        return

    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "Sam",
        "organization": "FlexFit Studio",
        "use_case": "appointment_cancellation",
        "client_id": client_id,
        "client_name": client_name,
        "appointment_id": appt_id,
        "appointment_start": start_raw,
        "late_cancel": is_late_cancel,
        "fields": {
            "phone": call.get_field("phone"),
            "cancel_type": cancel_type,
            "confirm_cancel": confirm,
        },
    }
    print(json.dumps(results, indent=2))
    logging.info("Appointment cancellation result saved.")

    late_note = (
        " As mentioned, a late cancellation fee may apply."
        if is_late_cancel else ""
    )
    call.hangup(
        final_instructions=(
            f"Confirm to {client_name} that their {cancel_type} on {display_time} "
            f"has been successfully cancelled.{late_note} Let them know we hope to see them "
            "at FlexFit Studio soon. Thank them for calling."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
