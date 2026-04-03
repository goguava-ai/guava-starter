import guava
import os
import logging
import json
import requests
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)

BASE_URL = "https://acuityscheduling.com/api/v1"
AUTH = (os.environ["ACUITY_USER_ID"], os.environ["ACUITY_API_KEY"])


def get_appointment_types() -> list:
    resp = requests.get(f"{BASE_URL}/appointment-types", auth=AUTH, timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_available_dates(appointment_type_id: int, month: str) -> list:
    """Returns available dates for the given appointment type and month (YYYY-MM)."""
    resp = requests.get(
        f"{BASE_URL}/availability/dates",
        auth=AUTH,
        params={"appointmentTypeID": appointment_type_id, "month": month},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def get_available_times(appointment_type_id: int, date: str) -> list:
    """Returns available time slots on a given date (YYYY-MM-DD)."""
    resp = requests.get(
        f"{BASE_URL}/availability/times",
        auth=AUTH,
        params={"appointmentTypeID": appointment_type_id, "date": date},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def create_appointment(
    appointment_type_id: int,
    date_time: str,
    first_name: str,
    last_name: str,
    email: str,
    phone: str,
) -> dict:
    """Books an appointment and returns the created appointment object."""
    resp = requests.post(
        f"{BASE_URL}/appointments",
        auth=AUTH,
        json={
            "appointmentTypeID": appointment_type_id,
            "datetime": date_time,  # ISO 8601, e.g. "2026-04-10T10:00:00-0500"
            "firstName": first_name,
            "lastName": last_name,
            "email": email,
            "phone": phone,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


class AppointmentBookingController(guava.CallController):
    def __init__(self):
        super().__init__()
        self.selected_slot = None
        self.appointment_type_id = int(os.environ.get("ACUITY_APPOINTMENT_TYPE_ID", "0"))

        # Pre-load appointment types to present to caller
        try:
            types = get_appointment_types()
            self.type_names = [t.get("name", "") for t in types if t.get("name")]
            if not self.appointment_type_id and types:
                self.appointment_type_id = types[0].get("id", 0)
        except Exception as e:
            logging.error("Failed to load appointment types: %s", e)
            self.type_names = []

        self.set_persona(
            organization_name="Wellspring Wellness",
            agent_name="Jordan",
            agent_purpose=(
                "to help clients book appointments at Wellspring Wellness"
            ),
        )

        type_context = (
            f"Ask what type of service they're looking for. Available options: {', '.join(self.type_names)}."
            if self.type_names
            else "Ask what type of service they're looking for."
        )

        self.set_task(
            objective=(
                "A client has called to book an appointment. Collect their preferences "
                "and find an available time."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Wellspring Wellness. This is Jordan. "
                    "I'd love to help you book an appointment today."
                ),
                guava.Field(
                    key="first_name",
                    field_type="text",
                    description="Ask for their first name.",
                    required=True,
                ),
                guava.Field(
                    key="last_name",
                    field_type="text",
                    description="Ask for their last name.",
                    required=True,
                ),
                guava.Field(
                    key="email",
                    field_type="text",
                    description="Ask for their email address (used for confirmation).",
                    required=True,
                ),
                guava.Field(
                    key="phone",
                    field_type="text",
                    description="Ask for their phone number.",
                    required=True,
                ),
                guava.Field(
                    key="service_type",
                    field_type="text",
                    description=type_context,
                    required=True,
                ),
                guava.Field(
                    key="preferred_date",
                    field_type="text",
                    description=(
                        "Ask what date works best for them. "
                        "Capture in YYYY-MM-DD format (e.g. 2026-04-15)."
                    ),
                    required=True,
                ),
            ],
            on_complete=self.find_and_offer_slot,
        )

        self.accept_call()

    def find_and_offer_slot(self):
        first_name = self.get_field("first_name")
        last_name = self.get_field("last_name")
        email = self.get_field("email")
        phone = self.get_field("phone")
        preferred_date = self.get_field("preferred_date") or ""

        logging.info(
            "Finding availability for %s %s on %s",
            first_name, last_name, preferred_date,
        )

        try:
            times = get_available_times(self.appointment_type_id, preferred_date)
            if not times:
                # Try the next day
                next_date = (
                    datetime.strptime(preferred_date, "%Y-%m-%d") + timedelta(days=1)
                ).strftime("%Y-%m-%d")
                times = get_available_times(self.appointment_type_id, next_date)
                if times:
                    preferred_date = next_date

            if times:
                self.selected_slot = times[0]
                slot_time = self.selected_slot.get("time", "")

                try:
                    dt = datetime.fromisoformat(slot_time)
                    display_time = dt.strftime("%A, %B %-d at %-I:%M %p")
                except (ValueError, AttributeError):
                    display_time = slot_time

                self.set_task(
                    objective=(
                        f"An available slot has been found for {first_name}. "
                        "Present the time and confirm."
                    ),
                    checklist=[
                        guava.Say(
                            f"Great news — I have an opening on {display_time}. "
                            "Would that work for you?"
                        ),
                        guava.Field(
                            key="confirmed",
                            field_type="multiple_choice",
                            description="Ask if they'd like to book this time.",
                            choices=["yes", "no"],
                            required=True,
                        ),
                    ],
                    on_complete=lambda: self.book_slot(
                        first_name, last_name, email, phone, slot_time, display_time
                    ),
                )
                return

            logging.info("No availability found near %s", preferred_date)
        except Exception as e:
            logging.error("Availability search failed: %s", e)

        self.hangup(
            final_instructions=(
                f"Apologize to {first_name} and let them know there's no availability near "
                "their preferred date. Ask them to call back or visit our website to check "
                "other times. Thank them for calling Wellspring Wellness."
            )
        )

    def book_slot(
        self,
        first_name: str,
        last_name: str,
        email: str,
        phone: str,
        slot_time: str,
        display_time: str,
    ):
        confirmed = self.get_field("confirmed") or ""

        if confirmed.lower() != "yes":
            self.hangup(
                final_instructions=(
                    f"Acknowledge that {first_name} would like a different time. "
                    "Invite them to call back or visit our website to browse all available times. "
                    "Thank them for calling."
                )
            )
            return

        booked = None
        try:
            booked = create_appointment(
                self.appointment_type_id,
                slot_time,
                first_name,
                last_name,
                email,
                phone,
            )
            logging.info("Appointment booked: %s", booked.get("id"))
        except Exception as e:
            logging.error("Failed to book appointment: %s", e)

        if booked:
            print(json.dumps(booked, indent=2))
            self.hangup(
                final_instructions=(
                    f"Confirm to {first_name} that their appointment at Wellspring Wellness "
                    f"has been booked for {display_time}. "
                    "Let them know a confirmation email has been sent to the address they provided. "
                    "Thank them and wish them a great day."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Apologize to {first_name} — there was an issue completing the booking. "
                    "Ask them to call back or visit the website to try again. "
                    "Thank them for their patience."
                )
            )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=AppointmentBookingController,
    )
