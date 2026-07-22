# SDK conformance: guava-sdk 0.34.0 (2026-07-21)
import argparse
import logging
import os
import secrets

import guava
import pymysql
import pymysql.cursors
from guava import logging_utils


def get_connection():
    return pymysql.connect(
        host=os.environ["MYSQL_HOST"],
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=os.environ["MYSQL_USER"],
        password=os.environ["MYSQL_PASSWORD"],
        database=os.environ["MYSQL_DATABASE"],
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def create_appointment(
    customer_name: str,
    customer_phone: str,
    customer_email: str,
    service_type: str,
    preferred_date: str,
    notes: str,
) -> str:
    """Inserts a new appointment and returns the confirmation code."""
    confirmation_code = "APT-" + secrets.token_hex(3).upper()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO appointments
                    (confirmation_code, customer_name, customer_phone, customer_email,
                     service_type, preferred_date, notes, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending', NOW())
                """,
                (
                    confirmation_code,
                    customer_name,
                    customer_phone,
                    customer_email,
                    service_type,
                    preferred_date,
                    notes or "",
                ),
            )
    return confirmation_code


agent = guava.Agent(
    name="Jordan",
    organization="Peak Outdoors",
    purpose=(
        "to help Peak Outdoors customers schedule gear service and repair appointments"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "appointment_booking",
        objective=(
            "A customer has called to book a gear service or repair appointment. "
            "Collect their contact information, the type of service they need, "
            "their preferred date, and any relevant notes, then save the appointment."
        ),
        checklist=[
            guava.Say(
                "Thanks for calling Peak Outdoors. I'm Jordan. "
                "I'd be happy to get a service appointment scheduled for you. "
                "Let me grab a few details."
            ),
            guava.Field(
                key="customer_name",
                field_type="text",
                description="Ask for their full name.",
                required=True,
            ),
            guava.Field(
                key="customer_phone",
                field_type="text",
                description="Ask for the best phone number to reach them.",
                required=True,
            ),
            guava.Field(
                key="customer_email",
                field_type="text",
                description="Ask for their email address to send the confirmation.",
                required=True,
            ),
            guava.Field(
                key="service_type",
                field_type="multiple_choice",
                description="Ask what type of service they need.",
                choices=[
                    "bike tune-up",
                    "bike repair",
                    "ski/snowboard tuning",
                    "boot fitting",
                    "kayak/paddleboard inspection",
                    "other gear service",
                ],
                required=True,
            ),
            guava.Field(
                key="preferred_date",
                field_type="text",
                description=(
                    "Ask what date they'd like to come in. "
                    "Capture their preference as a date string (e.g. 'next Tuesday', 'March 15th')."
                ),
                required=True,
            ),
            guava.Field(
                key="notes",
                field_type="text",
                description=(
                    "Ask if there's anything specific the technician should know about — "
                    "make/model, the issue they're experiencing, etc. Capture their answer or skip."
                ),
                required=False,
            ),
        ],
    )


@agent.on_task_complete("appointment_booking")
def on_appointment_booking_done(call: guava.Call) -> None:
    name = call.get_field("customer_name") or "Unknown"
    phone = call.get_field("customer_phone") or ""
    email = call.get_field("customer_email") or ""
    service = call.get_field("service_type") or "gear service"
    preferred_date = call.get_field("preferred_date") or "flexible"
    notes = call.get_field("notes") or ""

    logging.info(
        "Booking appointment for %s — service: %s, date: %s", name, service, preferred_date
    )

    try:
        confirmation_code = create_appointment(
            name, phone, email, service, preferred_date, notes
        )
        logging.info("Appointment created: %s for %s", confirmation_code, name)
        call.hangup(
            final_instructions=(
                f"Let {name} know their appointment has been booked. "
                f"Their confirmation code is {confirmation_code}. "
                f"Service: {service}. Preferred date: {preferred_date}. "
                "Let them know our team will confirm the exact time slot by email within one "
                "business day. Ask them to bring the gear in at least 15 minutes before their slot. "
                "Thank them for choosing Peak Outdoors."
            )
        )
    except Exception as e:
        logging.error("Failed to book appointment for %s: %s", name, e)
        call.hangup(
            final_instructions=(
                f"Apologize to {name} for a technical issue. Let them know their request has "
                "been noted and a team member will call them back within one business day to "
                "confirm the appointment. Thank them for their patience."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()

    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--phone", metavar="PHONE_NUMBER", nargs="?", const="", help="Listen for phone calls."
    )
    group.add_argument(
        "--webrtc", metavar="WEBRTC_CODE", nargs="?", const="", help="Listen on a WebRTC code."
    )
    group.add_argument("--local", action="store_true", help="Start a local call.")
    group.add_argument("--sip", metavar="SIP_CODE", help="Listen on a SIP code \'guavasip-...\'.")
    args = parser.parse_args()

    if args.phone is not None:
        agent.listen_phone(args.phone)
    elif args.webrtc is not None:
        agent.listen_webrtc(args.webrtc or None)
    elif args.sip:
        agent.listen_sip(args.sip)
    else:
        agent.call_local()
