import guava
import os
import logging
import json
import requests
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)

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


class AppointmentCancellationController(guava.CallController):
    def __init__(self):
        super().__init__()
        self.client_id = None
        self.client_name = None
        self.upcoming_visit = None
        self.is_late_cancel = False

        self.set_persona(
            organization_name="FlexFit Studio",
            agent_name="Sam",
            agent_purpose="to help FlexFit Studio members manage and cancel their class bookings and appointments",
        )

        self.set_task(
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
            on_complete=self.lookup_client,
        )

        self.accept_call()

    def lookup_client(self):
        phone = self.get_field("phone")
        cancel_type = self.get_field("cancel_type")

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
                self.hangup(
                    final_instructions=(
                        "Let the caller know we couldn't find an account matching that phone number. "
                        "Ask them to double-check the number on file, or reach out to the front desk "
                        "for help. Thank them for calling FlexFit Studio."
                    )
                )
                return

            client = clients[0]
            self.client_id = str(client.get("Id", ""))
            first_name = client.get("FirstName", "")
            last_name = client.get("LastName", "")
            self.client_name = f"{first_name} {last_name}".strip() or "there"
            logging.info("Found client: %s (ID: %s)", self.client_name, self.client_id)

        except Exception as e:
            logging.error("Failed to look up Mindbody client: %s", e)
            self.hangup(
                final_instructions=(
                    "Apologize and let them know we're having trouble reaching the member database "
                    "right now. Ask them to try again shortly or stop by the front desk."
                )
            )
            return

        # Route to the appropriate cancellation flow based on type.
        if cancel_type == "a class booking":
            self.fetch_upcoming_class()
        else:
            # For personal training or spa, fetch upcoming appointments.
            self.fetch_upcoming_appointment()

    def fetch_upcoming_class(self):
        """Fetch the member's most upcoming class visit so we can offer to cancel it."""
        today_str = datetime.now().date().isoformat()

        try:
            token = get_staff_token()
            resp = requests.get(
                f"{BASE_URL}/client/clientvisits",
                headers=get_headers(token),
                params={
                    "ClientID": self.client_id,
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
                logging.info("No upcoming class visits found for client %s.", self.client_id)
                self.hangup(
                    final_instructions=(
                        f"Let {self.client_name} know we couldn't find any upcoming class bookings "
                        "on their account. If they think there's a mistake, suggest they visit the "
                        "front desk or check their schedule online. Thank them for calling FlexFit Studio."
                    )
                )
                return

            self.upcoming_visit = upcoming[0]
            class_name = self.upcoming_visit.get("Name", "your class")
            start_raw = self.upcoming_visit.get("StartDateTime", "")

            try:
                dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
                display_time = dt.strftime("%A, %B %-d at %-I:%M %p")
                # Determine if this is a late cancellation.
                now_utc = datetime.now(timezone.utc)
                hours_until = (dt.astimezone(timezone.utc) - now_utc).total_seconds() / 3600
                self.is_late_cancel = hours_until < LATE_CANCEL_WINDOW_HOURS
            except (ValueError, AttributeError):
                display_time = start_raw
                self.is_late_cancel = False

            logging.info(
                "Most upcoming visit: %s on %s. Late cancel: %s",
                class_name, display_time, self.is_late_cancel,
            )

        except Exception as e:
            logging.error("Failed to fetch client visits: %s", e)
            self.hangup(
                final_instructions=(
                    "Apologize and let the caller know we're having trouble loading their schedule. "
                    "Ask them to try again shortly or contact the front desk."
                )
            )
            return

        # Build the late-cancel warning if needed, then ask for confirmation.
        class_name = self.upcoming_visit.get("Name", "your class")
        start_raw = self.upcoming_visit.get("StartDateTime", "")
        try:
            dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
            display_time = dt.strftime("%A, %B %-d at %-I:%M %p")
        except (ValueError, AttributeError):
            display_time = start_raw

        late_cancel_note = (
            " Please note that because this class starts in less than 12 hours, this will be "
            "recorded as a late cancellation, which may result in a fee or forfeiture of the "
            "class credit per our studio policy."
            if self.is_late_cancel else ""
        )

        self.set_task(
            objective=(
                f"Confirm with {self.client_name} which class to cancel and get their final decision."
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
            on_complete=self.execute_class_cancellation,
        )

    def execute_class_cancellation(self):
        confirm = self.get_field("confirm_cancel")
        class_name = self.upcoming_visit.get("Name", "your class")
        start_raw = self.upcoming_visit.get("StartDateTime", "")
        class_id = self.upcoming_visit.get("ClassId")

        try:
            dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
            display_time = dt.strftime("%A, %B %-d at %-I:%M %p")
        except (ValueError, AttributeError):
            display_time = start_raw

        if confirm != "yes, cancel it":
            self.hangup(
                final_instructions=(
                    f"Let {self.client_name} know their {class_name} booking on {display_time} "
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
                    "ClientId": self.client_id,
                    "ClassId": class_id,
                    "SendEmail": False,
                    "LateCancel": self.is_late_cancel,
                },
                timeout=10,
            )
            resp.raise_for_status()
            logging.info(
                "Removed client %s from class %s. Late cancel: %s",
                self.client_id, class_id, self.is_late_cancel,
            )
        except Exception as e:
            logging.error("Failed to remove client from class: %s", e)
            self.hangup(
                final_instructions=(
                    f"Apologize to {self.client_name} — we ran into a problem processing the "
                    "cancellation. Please ask them to try again or contact the front desk directly."
                )
            )
            return

        results = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "agent": "Sam",
            "organization": "FlexFit Studio",
            "use_case": "appointment_cancellation",
            "client_id": self.client_id,
            "client_name": self.client_name,
            "class_id": class_id,
            "class_name": class_name,
            "class_start": start_raw,
            "late_cancel": self.is_late_cancel,
            "fields": {
                "phone": self.get_field("phone"),
                "cancel_type": self.get_field("cancel_type"),
                "confirm_cancel": confirm,
            },
        }
        print(json.dumps(results, indent=2))
        logging.info("Cancellation result saved.")

        late_note = (
            " As mentioned, this will be marked as a late cancellation."
            if self.is_late_cancel else ""
        )
        self.hangup(
            final_instructions=(
                f"Confirm to {self.client_name} that their {class_name} class on {display_time} "
                f"has been successfully cancelled.{late_note} Let them know we'd love to see them "
                "at another class soon. Thank them for calling FlexFit Studio."
            )
        )

    def fetch_upcoming_appointment(self):
        """Fetch the member's most upcoming personal training or spa appointment."""
        cancel_type = self.get_field("cancel_type")
        today_str = datetime.now().date().isoformat()

        try:
            token = get_staff_token()
            resp = requests.get(
                f"{BASE_URL}/appointment/staffappointments",
                headers=get_headers(token),
                params={
                    "ClientId": self.client_id,
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
                logging.info("No upcoming appointments found for client %s.", self.client_id)
                self.hangup(
                    final_instructions=(
                        f"Let {self.client_name} know we couldn't find any upcoming {cancel_type} "
                        "bookings on their account. If they believe there's a mistake, ask them to "
                        "contact the front desk. Thank them for calling FlexFit Studio."
                    )
                )
                return

            appt = upcoming[0]
            appt_id = appt.get("Id")
            staff_name = appt.get("Staff", {}).get("Name", "your trainer")
            start_raw = appt.get("StartDateTime", "")

            try:
                dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
                display_time = dt.strftime("%A, %B %-d at %-I:%M %p")
                now_utc = datetime.now(timezone.utc)
                hours_until = (dt.astimezone(timezone.utc) - now_utc).total_seconds() / 3600
                self.is_late_cancel = hours_until < LATE_CANCEL_WINDOW_HOURS
            except (ValueError, AttributeError):
                display_time = start_raw
                self.is_late_cancel = False

            logging.info(
                "Most upcoming appointment: ID %s on %s with %s. Late cancel: %s",
                appt_id, display_time, staff_name, self.is_late_cancel,
            )

            # Store on self for use in cancellation step.
            self._pending_appt_id = appt_id
            self._pending_appt_display = display_time
            self._pending_staff_name = staff_name
            self._pending_start_raw = start_raw

        except Exception as e:
            logging.error("Failed to fetch appointments: %s", e)
            self.hangup(
                final_instructions=(
                    "Apologize and let the caller know we're having trouble loading their appointments. "
                    "Please ask them to contact the front desk for assistance."
                )
            )
            return

        late_cancel_note = (
            " Please be aware that since this appointment is within 12 hours, it will be marked "
            "as a late cancellation and a fee may apply per our studio policy."
            if self.is_late_cancel else ""
        )

        self.set_task(
            objective=(
                f"Confirm with {self.client_name} which appointment to cancel and get their decision."
            ),
            checklist=[
                guava.Say(
                    f"I found your upcoming {cancel_type} on {self._pending_appt_display} "
                    f"with {self._pending_staff_name}.{late_cancel_note} "
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
            on_complete=self.execute_appointment_cancellation,
        )

    def execute_appointment_cancellation(self):
        confirm = self.get_field("confirm_cancel")
        cancel_type = self.get_field("cancel_type")
        appt_id = self._pending_appt_id
        display_time = self._pending_appt_display
        start_raw = self._pending_start_raw

        if confirm != "yes, cancel it":
            self.hangup(
                final_instructions=(
                    f"Let {self.client_name} know their {cancel_type} on {display_time} "
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
                appt_id, self.client_id, self.is_late_cancel,
            )
        except Exception as e:
            logging.error("Failed to cancel appointment %s: %s", appt_id, e)
            self.hangup(
                final_instructions=(
                    f"Apologize to {self.client_name} — we couldn't complete the cancellation right now. "
                    "Please ask them to contact the front desk for assistance."
                )
            )
            return

        results = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "agent": "Sam",
            "organization": "FlexFit Studio",
            "use_case": "appointment_cancellation",
            "client_id": self.client_id,
            "client_name": self.client_name,
            "appointment_id": appt_id,
            "appointment_start": start_raw,
            "late_cancel": self.is_late_cancel,
            "fields": {
                "phone": self.get_field("phone"),
                "cancel_type": cancel_type,
                "confirm_cancel": confirm,
            },
        }
        print(json.dumps(results, indent=2))
        logging.info("Appointment cancellation result saved.")

        late_note = (
            " As mentioned, a late cancellation fee may apply."
            if self.is_late_cancel else ""
        )
        self.hangup(
            final_instructions=(
                f"Confirm to {self.client_name} that their {cancel_type} on {display_time} "
                f"has been successfully cancelled.{late_note} Let them know we hope to see them "
                "at FlexFit Studio soon. Thank them for calling."
            )
        )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=AppointmentCancellationController,
    )
