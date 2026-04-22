import guava
import os
import logging
from guava import logging_utils
import argparse
import requests
from datetime import datetime, timedelta


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
    if not resp.ok:
        return []
    return resp.json()


def create_appointment(
    appointment_type_id: int,
    date_time: str,
    first_name: str,
    last_name: str,
    email: str,
) -> dict | None:
    resp = requests.post(
        f"{BASE_URL}/appointments",
        auth=AUTH,
        json={
            "appointmentTypeID": appointment_type_id,
            "datetime": date_time,
            "firstName": first_name,
            "lastName": last_name,
            "email": email,
        },
        timeout=10,
    )
    if not resp.ok:
        return None
    return resp.json()


agent = guava.Agent(
    name="Jordan",
    organization="Wellspring Wellness",
    purpose="to follow up with clients who missed their appointment and help them rebook",
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("client_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    client_name = call.get_variable("client_name")
    appointment_id = call.get_variable("appointment_id")
    rebook_date = call.get_variable("rebook_date")

    if outcome == "unavailable":
        logging.info("Unable to reach %s for no-show followup.", client_name)
        call.hangup(
            final_instructions=(
                f"Leave a brief, warm voicemail for {client_name} from Wellspring Wellness. "
                "Let them know you noticed they missed their appointment and that you'd love to "
                "help them rebook whenever they're ready. Ask them to call back or visit the website. "
                "Keep it friendly — not guilt-inducing."
            )
        )
    elif outcome == "available":
        appointment = None
        try:
            appointment = get_appointment(appointment_id)
            logging.info("Loaded missed appointment %s", appointment_id)
        except Exception as e:
            logging.error("Failed to load appointment %s: %s", appointment_id, e)

        # Pre-load next available slot
        new_slot_time = None
        if appointment:
            appt_type_id = appointment.get("appointmentTypeID", 0)
            try:
                check_date = datetime.strptime(rebook_date, "%Y-%m-%d")
                for _ in range(7):
                    date_str = check_date.strftime("%Y-%m-%d")
                    times = get_available_times(appt_type_id, date_str)
                    if times:
                        new_slot_time = times[0].get("time", "")
                        break
                    check_date += timedelta(days=1)
            except Exception as e:
                logging.warning("Could not pre-load next slot: %s", e)

        call.set_variable("appointment", appointment)
        call.set_variable("appointment_id", appointment_id)
        call.set_variable("new_slot_time", new_slot_time)

        appt_type = appointment.get("type", "appointment") if appointment else "appointment"
        appt_date = appointment.get("date", "their recent appointment") if appointment else "their recent appointment"

        new_time_display = ""
        if new_slot_time:
            try:
                dt = datetime.fromisoformat(new_slot_time)
                new_time_display = dt.strftime("%A, %B %-d at %-I:%M %p")
            except (ValueError, AttributeError):
                new_time_display = new_slot_time

        call.set_variable("new_time_display", new_time_display)

        call.set_task(
            "no_show_followup",
            objective=(
                f"Follow up with {client_name} who missed their {appt_type} on {appt_date}. "
                "Check in on how they're doing and offer to rebook."
            ),
            checklist=[
                guava.Say(
                    f"Hi {client_name}, this is Jordan calling from Wellspring Wellness. "
                    f"We noticed you weren't able to make your {appt_type} on {appt_date}. "
                    "I just wanted to check in and see how you're doing."
                ),
                guava.Field(
                    key="reason",
                    field_type="multiple_choice",
                    description="Ask if everything is okay and whether there was a reason they missed it.",
                    choices=["forgot", "something came up", "feeling unwell", "no longer interested", "other"],
                    required=True,
                ),
                guava.Field(
                    key="wants_to_rebook",
                    field_type="multiple_choice",
                    description=(
                        "Ask if they'd like to rebook. "
                        + (f"Mention you have an opening on {new_time_display}. " if new_time_display else "")
                    ),
                    choices=["yes", "no"],
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("no_show_followup")
def handle_rebook(call: guava.Call) -> None:
    client_name = call.get_variable("client_name")
    reason = call.get_field("reason") or ""
    wants_rebook = call.get_field("wants_to_rebook") or ""
    appointment = call.get_variable("appointment")
    new_slot_time = call.get_variable("new_slot_time")
    new_time_display = call.get_variable("new_time_display")
    appointment_id = call.get_variable("appointment_id")
    appt_type = appointment.get("type", "appointment") if appointment else "appointment"

    logging.info(
        "No-show followup for %s: reason=%s, wants_rebook=%s",
        client_name, reason, wants_rebook,
    )

    if "yes" not in wants_rebook:
        call.hangup(
            final_instructions=(
                f"Thank {client_name} for their time. Let them know they're always welcome "
                "to rebook anytime by visiting the website or calling us. Wish them well."
            )
        )
        return

    if not new_slot_time or not appointment:
        call.hangup(
            final_instructions=(
                f"Let {client_name} know we'd love to have them back. "
                "Ask them to visit the website or call back to pick a time that works. "
                "Thank them for their time."
            )
        )
        return

    first_name = appointment.get("firstName", client_name.split()[0])
    last_name = appointment.get("lastName", "")
    email = appointment.get("email", "")
    appt_type_id = appointment.get("appointmentTypeID", 0)

    booked = None
    try:
        booked = create_appointment(appt_type_id, new_slot_time, first_name, last_name, email)
        logging.info("Rebooked appointment: %s", booked.get("id") if booked else None)
    except Exception as e:
        logging.error("Failed to rebook appointment: %s", e)

    if booked:
        call.hangup(
            final_instructions=(
                f"Let {client_name} know their {appt_type} has been rebooked for {new_time_display}. "
                "A confirmation email is on its way. Thank them for giving us another chance "
                "and wish them a great day."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Apologize — the rebooking couldn't be completed online. "
                "Invite {client_name} to call back or visit the website to book. "
                "Thank them for their time."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound no-show followup call via Acuity Scheduling."
    )
    parser.add_argument("phone", help="Client phone number (E.164)")
    parser.add_argument("--name", required=True, help="Client's full name")
    parser.add_argument("--appointment-id", required=True, help="Acuity appointment ID that was missed")
    parser.add_argument("--rebook-date", default="", help="Preferred rebook date in YYYY-MM-DD format")
    args = parser.parse_args()

    rebook_date = args.rebook_date or (datetime.today() + timedelta(days=2)).strftime("%Y-%m-%d")

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "client_name": args.name,
            "appointment_id": args.appointment_id,
            "rebook_date": rebook_date,
        },
    )
