import guava
import os
import logging
from guava import logging_utils
import argparse
import requests
from datetime import datetime


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


class NoShowFollowupController(guava.CallController):
    def __init__(self, client_name: str, appointment_id: str, rebook_date: str):
        super().__init__()
        self.client_name = client_name
        self.appointment_id = appointment_id
        self.rebook_date = rebook_date
        self.appointment = None
        self.new_slot_time = None

        try:
            self.appointment = get_appointment(appointment_id)
            logging.info("Loaded missed appointment %s", appointment_id)
        except Exception as e:
            logging.error("Failed to load appointment %s: %s", appointment_id, e)

        # Pre-load next available slot
        if self.appointment:
            appt_type_id = self.appointment.get("appointmentTypeID", 0)
            try:
                from datetime import datetime, timedelta
                check_date = datetime.strptime(rebook_date, "%Y-%m-%d")
                for _ in range(7):
                    date_str = check_date.strftime("%Y-%m-%d")
                    times = get_available_times(appt_type_id, date_str)
                    if times:
                        self.new_slot_time = times[0].get("time", "")
                        break
                    check_date += timedelta(days=1)
            except Exception as e:
                logging.warning("Could not pre-load next slot: %s", e)

        self.set_persona(
            organization_name="Wellspring Wellness",
            agent_name="Jordan",
            agent_purpose=(
                "to follow up with clients who missed their appointment and help them rebook"
            ),
        )

        appt_type = self.appointment.get("type", "appointment") if self.appointment else "appointment"
        appt_date = self.appointment.get("date", "their recent appointment") if self.appointment else "their recent appointment"

        self.reach_person(
            contact_full_name=self.client_name,
            on_success=lambda: self.begin_followup(appt_type, appt_date),
            on_failure=self.leave_voicemail,
        )

    def begin_followup(self, appt_type: str, appt_date: str):
        new_time_display = ""
        if self.new_slot_time:
            try:
                dt = datetime.fromisoformat(self.new_slot_time)
                new_time_display = dt.strftime("%A, %B %-d at %-I:%M %p")
            except (ValueError, AttributeError):
                new_time_display = self.new_slot_time

        self.set_task(
            objective=(
                f"Follow up with {self.client_name} who missed their {appt_type} on {appt_date}. "
                "Check in on how they're doing and offer to rebook."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.client_name}, this is Jordan calling from Wellspring Wellness. "
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
            on_complete=lambda: self.handle_rebook(new_time_display),
        )

    def handle_rebook(self, new_time_display: str):
        reason = self.get_field("reason") or ""
        wants_rebook = self.get_field("wants_to_rebook") or ""
        appt_type = self.appointment.get("type", "appointment") if self.appointment else "appointment"

        logging.info(
            "No-show followup for %s: reason=%s, wants_rebook=%s",
            self.client_name, reason, wants_rebook,
        )

        if "yes" not in wants_rebook:
            self.hangup(
                final_instructions=(
                    f"Thank {self.client_name} for their time. Let them know they're always welcome "
                    "to rebook anytime by visiting the website or calling us. Wish them well."
                )
            )
            return

        if not self.new_slot_time or not self.appointment:
            self.hangup(
                final_instructions=(
                    f"Let {self.client_name} know we'd love to have them back. "
                    "Ask them to visit the website or call back to pick a time that works. "
                    "Thank them for their time."
                )
            )
            return

        first_name = self.appointment.get("firstName", self.client_name.split()[0])
        last_name = self.appointment.get("lastName", "")
        email = self.appointment.get("email", "")
        appt_type_id = self.appointment.get("appointmentTypeID", 0)

        booked = None
        try:
            booked = create_appointment(appt_type_id, self.new_slot_time, first_name, last_name, email)
            logging.info("Rebooked appointment: %s", booked.get("id") if booked else None)
        except Exception as e:
            logging.error("Failed to rebook appointment: %s", e)

        if booked:
            self.hangup(
                final_instructions=(
                    f"Let {self.client_name} know their {appt_type} has been rebooked for {new_time_display}. "
                    "A confirmation email is on its way. Thank them for giving us another chance "
                    "and wish them a great day."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Apologize — the rebooking couldn't be completed online. "
                    "Invite {self.client_name} to call back or visit the website to book. "
                    "Thank them for their time."
                )
            )

    def leave_voicemail(self):
        logging.info("Unable to reach %s for no-show followup.", self.client_name)
        self.hangup(
            final_instructions=(
                f"Leave a brief, warm voicemail for {self.client_name} from Wellspring Wellness. "
                "Let them know you noticed they missed their appointment and that you'd love to "
                "help them rebook whenever they're ready. Ask them to call back or visit the website. "
                "Keep it friendly — not guilt-inducing."
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

    from datetime import datetime, timedelta
    rebook_date = args.rebook_date or (datetime.today() + timedelta(days=2)).strftime("%Y-%m-%d")

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=NoShowFollowupController(
            client_name=args.name,
            appointment_id=args.appointment_id,
            rebook_date=rebook_date,
        ),
    )
