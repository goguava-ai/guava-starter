import guava
import os
import logging
from guava import logging_utils
import requests
from datetime import datetime, timedelta


BASE_URL = "https://acuityscheduling.com/api/v1"
AUTH = (os.environ["ACUITY_USER_ID"], os.environ["ACUITY_API_KEY"])


def get_appointment_types() -> list:
    resp = requests.get(f"{BASE_URL}/appointment-types", auth=AUTH, timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_available_dates(appointment_type_id: int, month: str) -> list:
    resp = requests.get(
        f"{BASE_URL}/availability/dates",
        auth=AUTH,
        params={"appointmentTypeID": appointment_type_id, "month": month},
        timeout=10,
    )
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


class AvailabilityCheckController(guava.CallController):
    def __init__(self):
        super().__init__()
        self.appointment_type_id = int(os.environ.get("ACUITY_APPOINTMENT_TYPE_ID", "0"))

        try:
            types = get_appointment_types()
            self.type_map = {t["name"].lower(): t["id"] for t in types if t.get("name") and t.get("id")}
            self.type_names = list(self.type_map.keys())
            if not self.appointment_type_id and types:
                self.appointment_type_id = types[0].get("id", 0)
        except Exception as e:
            logging.error("Failed to load appointment types: %s", e)
            self.type_map = {}
            self.type_names = []

        self.set_persona(
            organization_name="Wellspring Wellness",
            agent_name="Jordan",
            agent_purpose=(
                "to help callers find the next available appointment time at Wellspring Wellness"
            ),
        )

        type_hint = (
            f"Options: {', '.join(self.type_names)}." if self.type_names else ""
        )

        self.set_task(
            objective=(
                "A caller wants to know the next available appointment time. "
                "Collect their service preference and preferred timeframe, then look up availability."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Wellspring Wellness. This is Jordan. "
                    "I can help you find the next available appointment."
                ),
                guava.Field(
                    key="service_type",
                    field_type="text",
                    description=f"Ask what type of service or appointment they're looking for. {type_hint}",
                    required=True,
                ),
                guava.Field(
                    key="preferred_week",
                    field_type="text",
                    description=(
                        "Ask when they'd like to come in — this week, next week, or a specific date. "
                        "Capture as a date in YYYY-MM-DD format or a relative phrase like 'next Monday'."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="preferred_time_of_day",
                    field_type="multiple_choice",
                    description="Ask whether they prefer morning, afternoon, or have no preference.",
                    choices=["morning", "afternoon", "no preference"],
                    required=True,
                ),
            ],
            on_complete=self.lookup_availability,
        )

        self.accept_call()

    def lookup_availability(self):
        service_type = (self.get_field("service_type") or "").lower()
        preferred_week = self.get_field("preferred_week") or ""
        preferred_time = self.get_field("preferred_time_of_day") or ""

        # Resolve appointment type ID from service name if possible
        appt_type_id = self.appointment_type_id
        for name, type_id in self.type_map.items():
            if service_type in name or name in service_type:
                appt_type_id = type_id
                break

        # Resolve start date
        today = datetime.today()
        try:
            start_date = datetime.strptime(preferred_week, "%Y-%m-%d")
        except (ValueError, AttributeError):
            start_date = today

        logging.info("Checking availability for type %s starting %s", appt_type_id, start_date.strftime("%Y-%m-%d"))

        available_slots = []
        try:
            for i in range(14):
                check_date = start_date + timedelta(days=i)
                date_str = check_date.strftime("%Y-%m-%d")
                times = get_available_times(appt_type_id, date_str)
                if times:
                    # Filter by time of day preference
                    for slot in times:
                        t = slot.get("time", "")
                        try:
                            dt = datetime.fromisoformat(t)
                            hour = dt.hour
                            if preferred_time == "morning" and hour >= 12:
                                continue
                            if preferred_time == "afternoon" and hour < 12:
                                continue
                            available_slots.append(slot)
                        except (ValueError, AttributeError):
                            available_slots.append(slot)
                    if available_slots:
                        break
        except Exception as e:
            logging.error("Availability lookup failed: %s", e)

        if available_slots:
            slot = available_slots[0]
            slot_time = slot.get("time", "")
            try:
                dt = datetime.fromisoformat(slot_time)
                display_time = dt.strftime("%A, %B %-d at %-I:%M %p")
            except (ValueError, AttributeError):
                display_time = slot_time

            additional = ""
            if len(available_slots) > 1:
                try:
                    dt2 = datetime.fromisoformat(available_slots[1].get("time", ""))
                    additional = f" I also have {dt2.strftime('%A, %B %-d at %-I:%M %p')} if that works better."
                except (ValueError, AttributeError):
                    pass

            self.hangup(
                final_instructions=(
                    f"Let the caller know the next available time matching their preference is "
                    f"{display_time}.{additional} "
                    "Invite them to call back or visit the website to book. "
                    "Wish them a great day."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    "Let the caller know there's no availability matching their preferences in the "
                    "next two weeks. Invite them to check the website for live availability or "
                    "call back to check a different time range. Thank them for calling."
                )
            )


if __name__ == "__main__":
    logging_utils.configure_logging()
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=AvailabilityCheckController,
    )
