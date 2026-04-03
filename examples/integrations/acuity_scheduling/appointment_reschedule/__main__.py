import guava
import os
import logging
import argparse
import requests
from datetime import datetime

logging.basicConfig(level=logging.INFO)

BASE_URL = "https://acuityscheduling.com/api/v1"
AUTH = (os.environ["ACUITY_USER_ID"], os.environ["ACUITY_API_KEY"])


def get_appointment(appointment_id: str) -> dict | None:
    resp = requests.get(f"{BASE_URL}/appointments/{appointment_id}", auth=AUTH, timeout=10)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def get_available_times(appointment_type_id: int, date: str) -> list:
    resp = requests.get(
        f"{BASE_URL}/availability/times",
        auth=AUTH,
        params={"appointmentTypeID": appointment_type_id, "date": date},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def reschedule_appointment(appointment_id: str, new_datetime: str) -> dict | None:
    resp = requests.put(
        f"{BASE_URL}/appointments/{appointment_id}/reschedule",
        auth=AUTH,
        json={"datetime": new_datetime},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


class AppointmentRescheduleController(guava.CallController):
    def __init__(self, client_name: str, appointment_id: str):
        super().__init__()
        self.client_name = client_name
        self.appointment_id = appointment_id
        self.appointment = None
        self.new_slot_time = None

        try:
            self.appointment = get_appointment(appointment_id)
            logging.info("Loaded appointment %s for rescheduling.", appointment_id)
        except Exception as e:
            logging.error("Failed to load appointment %s: %s", appointment_id, e)

        self.set_persona(
            organization_name="Wellspring Wellness",
            agent_name="Jordan",
            agent_purpose=(
                "to help clients reschedule their Wellspring Wellness appointments"
            ),
        )

        appt_display = ""
        if self.appointment:
            appt_date = self.appointment.get("date", "")
            appt_time = self.appointment.get("time", "")
            appt_type = self.appointment.get("type", "appointment")
            try:
                dt = datetime.fromisoformat(f"{appt_date}T{appt_time}")
                appt_display = f"their {appt_type} on {dt.strftime('%A, %B %-d at %-I:%M %p')}"
            except (ValueError, AttributeError):
                appt_display = f"their {appt_type} on {appt_date}"

        self.set_task(
            objective=(
                f"Help {client_name} reschedule {appt_display or 'their appointment'}. "
                "Collect their preferred new date and find an available time."
            ),
            checklist=[
                guava.Say(
                    f"Hi {client_name}, this is Jordan from Wellspring Wellness. "
                    f"I understand you'd like to reschedule {appt_display or 'your appointment'}. "
                    "I'm happy to help with that."
                ),
                guava.Field(
                    key="new_preferred_date",
                    field_type="text",
                    description=(
                        "Ask what new date works best for them. "
                        "Capture in YYYY-MM-DD format."
                    ),
                    required=True,
                ),
            ],
            on_complete=self.find_new_slot,
        )

        self.accept_call()

    def find_new_slot(self):
        new_date = self.get_field("new_preferred_date") or ""
        appointment_type_id = self.appointment.get("appointmentTypeID", 0) if self.appointment else 0

        logging.info("Searching availability for %s on %s", self.client_name, new_date)

        try:
            times = get_available_times(appointment_type_id, new_date)
            if times:
                self.new_slot_time = times[0].get("time", "")
                try:
                    dt = datetime.fromisoformat(self.new_slot_time)
                    display_time = dt.strftime("%A, %B %-d at %-I:%M %p")
                except (ValueError, AttributeError):
                    display_time = self.new_slot_time

                self.set_task(
                    objective=(
                        f"A new slot has been found for {self.client_name}. "
                        "Present it and ask for confirmation."
                    ),
                    checklist=[
                        guava.Say(
                            f"I have an opening on {display_time}. "
                            "Would that work for you?"
                        ),
                        guava.Field(
                            key="confirmed",
                            field_type="multiple_choice",
                            description="Ask if the new time works for them.",
                            choices=["yes", "no"],
                            required=True,
                        ),
                    ],
                    on_complete=lambda: self.complete_reschedule(display_time),
                )
                return

        except Exception as e:
            logging.error("Availability search failed: %s", e)

        self.hangup(
            final_instructions=(
                f"Apologize to {self.client_name} — there's no availability on their preferred date. "
                "Ask them to visit the website or call back during business hours to find a time. "
                "Thank them for their patience."
            )
        )

    def complete_reschedule(self, display_time: str):
        confirmed = self.get_field("confirmed") or ""

        if confirmed.lower() != "yes":
            self.hangup(
                final_instructions=(
                    f"Acknowledge that {self.client_name} would like a different time. "
                    "Invite them to visit the website or call back. Thank them."
                )
            )
            return

        rescheduled = None
        try:
            rescheduled = reschedule_appointment(self.appointment_id, self.new_slot_time)
            logging.info("Appointment %s rescheduled: %s", self.appointment_id, rescheduled.get("id") if rescheduled else None)
        except Exception as e:
            logging.error("Reschedule failed for %s: %s", self.appointment_id, e)

        if rescheduled:
            self.hangup(
                final_instructions=(
                    f"Confirm to {self.client_name} that their appointment has been rescheduled "
                    f"to {display_time}. Let them know a new confirmation email is on its way. "
                    "Thank them and wish them a great day."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Apologize to {self.client_name} — the reschedule couldn't be completed online. "
                    "Ask them to call back during business hours and we'll sort it out. "
                    "Thank them for their patience."
                )
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Inbound appointment reschedule via Acuity Scheduling."
    )
    parser.add_argument("phone", help="Client phone number (E.164)")
    parser.add_argument("--name", required=True, help="Client's full name")
    parser.add_argument("--appointment-id", required=True, help="Acuity appointment ID to reschedule")
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=AppointmentRescheduleController(
            client_name=args.name,
            appointment_id=args.appointment_id,
        ),
    )
