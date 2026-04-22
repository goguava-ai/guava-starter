import guava
import os
import logging
from guava import logging_utils
from datetime import datetime, timezone
import firebase_admin
from firebase_admin import credentials, firestore


cred = credentials.Certificate(os.environ["GOOGLE_APPLICATION_CREDENTIALS"])
firebase_admin.initialize_app(cred)
db = firestore.client()

APPOINTMENTS_COLLECTION = os.environ.get("FIRESTORE_APPOINTMENTS_COLLECTION", "appointments")
BUSINESS_NAME = os.environ.get("BUSINESS_NAME", "Crestline Services")


def create_appointment(data: dict) -> str:
    """Write the appointment to Firestore and return the document ID."""
    data["created_at"] = firestore.SERVER_TIMESTAMP
    data["status"] = "confirmed"
    data["source"] = "voice"
    _, doc_ref = db.collection(APPOINTMENTS_COLLECTION).add(data)
    return doc_ref.id


def check_slot_availability(date_str: str, time_str: str, service_type: str) -> bool:
    """Return True if the requested slot is not already booked."""
    existing = (
        db.collection(APPOINTMENTS_COLLECTION)
        .where("date", "==", date_str)
        .where("time", "==", time_str)
        .where("service_type", "==", service_type)
        .where("status", "==", "confirmed")
        .limit(1)
        .stream()
    )
    return not any(True for _ in existing)


class AppointmentBookingController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name=BUSINESS_NAME,
            agent_name="Jordan",
            agent_purpose=(
                f"to help {BUSINESS_NAME} customers schedule appointments"
            ),
        )

        self.set_task(
            objective=(
                "A customer is calling to book an appointment. Collect their contact "
                "information, service type, and preferred date and time, then confirm the booking."
            ),
            checklist=[
                guava.Say(
                    f"Thank you for calling {BUSINESS_NAME}. This is Jordan. "
                    "I'd be happy to get an appointment scheduled for you."
                ),
                guava.Field(
                    key="customer_name",
                    field_type="text",
                    description="Ask for the customer's full name.",
                    required=True,
                ),
                guava.Field(
                    key="customer_phone",
                    field_type="text",
                    description="Ask for a callback phone number in case we need to reach them.",
                    required=True,
                ),
                guava.Field(
                    key="customer_email",
                    field_type="text",
                    description="Ask for their email address to send a confirmation.",
                    required=False,
                ),
                guava.Field(
                    key="service_type",
                    field_type="multiple_choice",
                    description="Ask what type of service they'd like to schedule.",
                    choices=[
                        "initial consultation",
                        "follow-up appointment",
                        "maintenance visit",
                        "inspection",
                        "other",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="preferred_date",
                    field_type="text",
                    description=(
                        "Ask for their preferred date. Capture it in a clear format "
                        "like 'Monday April 7' or '04/07/2026'."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="preferred_time",
                    field_type="multiple_choice",
                    description="Ask for their preferred time of day.",
                    choices=["morning (9am–12pm)", "afternoon (12pm–5pm)", "flexible"],
                    required=True,
                ),
                guava.Field(
                    key="special_notes",
                    field_type="text",
                    description=(
                        "Ask if there's anything specific we should know before the appointment — "
                        "access instructions, special requirements, etc."
                    ),
                    required=False,
                ),
            ],
            on_complete=self.book_appointment,
        )

        self.accept_call()

    def book_appointment(self):
        name = self.get_field("customer_name") or "Customer"
        phone = self.get_field("customer_phone") or ""
        email = self.get_field("customer_email") or ""
        service = self.get_field("service_type") or "other"
        date_str = self.get_field("preferred_date") or ""
        time_str = self.get_field("preferred_time") or "flexible"
        notes = self.get_field("special_notes") or ""

        logging.info(
            "Booking appointment for %s — service: %s, date: %s, time: %s",
            name, service, date_str, time_str,
        )

        try:
            available = check_slot_availability(date_str, time_str, service)
        except Exception as e:
            logging.warning("Availability check failed: %s", e)
            available = True  # Proceed optimistically; staff will confirm

        if not available:
            self.hangup(
                final_instructions=(
                    f"Let {name} know that the requested slot ({time_str} on {date_str}) "
                    "is already booked. Apologize and let them know someone from our scheduling "
                    "team will call them back within one business day to find an alternative time. "
                    "Their contact information has been noted."
                )
            )
            return

        appointment_data = {
            "customer_name": name,
            "customer_phone": phone,
            "customer_email": email,
            "service_type": service,
            "date": date_str,
            "time": time_str,
            "notes": notes,
        }

        try:
            appt_id = create_appointment(appointment_data)
            logging.info("Appointment created in Firestore: %s", appt_id)

            email_note = (
                f" A confirmation will be sent to {email}." if email else ""
            )

            self.hangup(
                final_instructions=(
                    f"Let {name} know their {service} appointment has been confirmed for "
                    f"{time_str} on {date_str}.{email_note} "
                    "Let them know they can call back if they need to reschedule. "
                    "Thank them for choosing " + BUSINESS_NAME + "."
                )
            )
        except Exception as e:
            logging.error("Failed to create appointment in Firestore: %s", e)
            self.hangup(
                final_instructions=(
                    f"Apologize to {name} for a system issue. Let them know their request "
                    "has been noted and a team member will call back within one business day "
                    "to confirm the appointment. Thank them for their patience."
                )
            )


if __name__ == "__main__":
    logging_utils.configure_logging()
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=AppointmentBookingController,
    )
