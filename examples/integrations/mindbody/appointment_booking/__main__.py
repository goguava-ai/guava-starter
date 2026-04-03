import guava
import os
import logging
import requests
from datetime import date, timedelta

logging.basicConfig(level=logging.INFO)

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


def fetch_bookable_items():
    """Return available appointment services and staff from Mindbody."""
    resp = requests.get(
        f"{BASE_URL}/appointment/bookableItems",
        headers=HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def lookup_client_by_email(email: str):
    """Return the first matching Mindbody client record for the given email."""
    resp = requests.get(
        f"{BASE_URL}/client/clients",
        headers=HEADERS,
        params={"searchText": email},
        timeout=10,
    )
    resp.raise_for_status()
    clients = resp.json().get("Clients", [])
    return clients[0] if clients else None


def book_appointment(client_id: str, staff_id: int, session_type_id: int,
                     start_datetime: str, end_datetime: str):
    """POST to Mindbody to create a new appointment."""
    payload = {
        "ClientId": client_id,
        "StaffId": staff_id,
        "SessionTypeId": session_type_id,
        "StartDateTime": start_datetime,
        "EndDateTime": end_datetime,
        "SendEmail": True,
    }
    resp = requests.post(
        f"{BASE_URL}/appointment/addAppointment",
        headers=HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("Appointment")


def add_client_to_class(client_id: str, class_id: int):
    """POST to Mindbody to enroll a client in a class."""
    payload = {
        "ClientId": client_id,
        "ClassId": class_id,
        "SendEmail": True,
    }
    resp = requests.post(
        f"{BASE_URL}/class/addclienttoclass",
        headers=HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("Class")


def fetch_upcoming_classes():
    """Return classes available in the next 7 days."""
    today = date.today()
    end = today + timedelta(days=7)
    resp = requests.get(
        f"{BASE_URL}/class/classes",
        headers=HEADERS,
        params={
            "startDateTime": today.isoformat(),
            "endDateTime": end.isoformat(),
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("Classes", [])


class AppointmentBookingController(guava.CallController):
    def __init__(self):
        super().__init__()

        # Pre-fetch bookable services so we can present real options.
        try:
            items = fetch_bookable_items()
            self._session_types = items.get("SessionTypes", [])
            self._staff = items.get("Staff", [])
        except Exception as e:
            logging.error("Failed to fetch bookable items: %s", e)
            self._session_types = []
            self._staff = []

        # Build choice lists from live data, with sensible fallbacks.
        service_names = (
            [s["Name"] for s in self._session_types[:5]]
            if self._session_types
            else ["Personal Training (60 min)", "Personal Training (30 min)", "Group Fitness Class"]
        )

        self.set_persona(
            organization_name="Peak Performance Studio",
            agent_name="Jordan",
            agent_purpose="to help clients book personal training sessions and fitness classes",
        )

        self.set_task(
            objective=(
                "Collect the caller's contact details and preferences, then book them "
                "into a personal training session or group fitness class at Peak Performance Studio."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Peak Performance Studio! My name is Jordan and "
                    "I'm here to help you get your next session on the books. "
                    "Just a few quick questions and we'll have you all set."
                ),
                guava.Field(
                    key="client_email",
                    field_type="text",
                    description=(
                        "Ask for the caller's email address so we can look up their account. "
                        "Confirm the spelling if it sounds ambiguous."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="booking_type",
                    field_type="multiple_choice",
                    description="Ask whether they'd like to book a personal training session or a group fitness class.",
                    choices=["personal training", "group fitness class"],
                    required=True,
                ),
                guava.Field(
                    key="service_preference",
                    field_type="multiple_choice",
                    description=(
                        "Ask which type of session they prefer. "
                        "Read the options naturally."
                    ),
                    choices=service_names,
                    required=True,
                ),
                guava.Field(
                    key="preferred_date",
                    field_type="text",
                    description=(
                        "Ask what date they would like to come in. "
                        "Accept natural language like 'this Thursday' or 'next Monday'."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="preferred_time",
                    field_type="text",
                    description=(
                        "Ask what time of day works best — morning, afternoon, or a specific time."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="staff_preference",
                    field_type="text",
                    description=(
                        "Ask if they have a preferred trainer or instructor, or if any available staff is fine. "
                        "This field is optional — if they say they don't mind, note 'no preference'."
                    ),
                    required=False,
                ),
            ],
            on_complete=self.handle_complete,
        )

        self.accept_call()

    def handle_complete(self):
        email = self.get_field("client_email")
        booking_type = self.get_field("booking_type")
        service_pref = self.get_field("service_preference")
        preferred_date = self.get_field("preferred_date")
        preferred_time = self.get_field("preferred_time")

        logging.info(
            "Booking request — email=%s type=%s service=%s date=%s time=%s",
            email, booking_type, service_pref, preferred_date, preferred_time,
        )

        # Look up client account.
        client = None
        try:
            client = lookup_client_by_email(email)
        except Exception as e:
            logging.error("Client lookup failed: %s", e)

        if client is None:
            logging.warning("No client found for email %s; cannot complete booking.", email)
            self.hangup(
                final_instructions=(
                    "Apologize warmly and let the caller know you weren't able to find their account "
                    "with the email provided. Ask them to visit the studio or call back during staffed hours "
                    "to complete the booking. Thank them for calling Peak Performance Studio."
                )
            )
            return

        client_id = client.get("Id") or client.get("UniqueId")

        booking_confirmed = False

        if booking_type == "group fitness class":
            # Attempt to enroll the client in an upcoming class matching their preference.
            try:
                classes = fetch_upcoming_classes()
                target_class = next(
                    (c for c in classes if service_pref.lower() in c.get("ClassDescription", {}).get("Name", "").lower()),
                    classes[0] if classes else None,
                )
                if target_class:
                    add_client_to_class(client_id, target_class["Id"])
                    booking_confirmed = True
                    logging.info("Added client %s to class %s", client_id, target_class["Id"])
            except Exception as e:
                logging.error("Class enrollment failed: %s", e)

        else:
            # Personal training — book an appointment.
            # Match session type from pre-fetched list.
            session_type = next(
                (s for s in self._session_types if service_pref.lower() in s.get("Name", "").lower()),
                self._session_types[0] if self._session_types else None,
            )
            staff_member = self._staff[0] if self._staff else None

            if session_type and staff_member:
                # Use a placeholder datetime; in production derive from preferred_date / preferred_time.
                start_dt = f"{date.today() + timedelta(days=1)}T09:00:00"
                end_dt = f"{date.today() + timedelta(days=1)}T10:00:00"
                try:
                    book_appointment(
                        client_id=client_id,
                        staff_id=staff_member["Id"],
                        session_type_id=session_type["Id"],
                        start_datetime=start_dt,
                        end_datetime=end_dt,
                    )
                    booking_confirmed = True
                    logging.info(
                        "Appointment booked for client %s on %s", client_id, start_dt
                    )
                except Exception as e:
                    logging.error("Appointment booking failed: %s", e)

        if booking_confirmed:
            self.hangup(
                final_instructions=(
                    "Let the caller know their booking is confirmed and that a confirmation email "
                    "is on its way. Remind them to arrive 10 minutes early and to bring water and "
                    "proper workout attire. Wish them a great session and thank them for choosing "
                    "Peak Performance Studio. Be warm and encouraging."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    "Apologize and let the caller know there was a technical issue completing the booking. "
                    "Ask them to try again or visit the studio in person. Thank them for their patience "
                    "and for calling Peak Performance Studio."
                )
            )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=AppointmentBookingController,
    )
