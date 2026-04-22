import guava
import os
import logging
import json
import requests
from datetime import datetime, timezone, timedelta

logging.basicConfig(level=logging.INFO)

BASE_URL = "https://api.mindbodyonline.com/public/v6"
API_KEY = os.environ["MINDBODY_API_KEY"]
SITE_ID = os.environ["MINDBODY_SITE_ID"]

# Time-of-day hour boundaries used when filtering class start times.
TIME_WINDOWS = {
    "morning": (5, 12),
    "afternoon": (12, 17),
    "evening": (17, 22),
}


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


class ClassBookingController(guava.CallController):
    def __init__(self):
        super().__init__()
        self.client_id = None
        self.client_name = None
        self.selected_class = None

        self.set_persona(
            organization_name="FlexFit Studio",
            agent_name="Jordan",
            agent_purpose="to help FlexFit Studio members book fitness classes and manage their schedules",
        )

        self.set_task(
            objective=(
                "A FlexFit Studio member has called to book a fitness class. Greet them warmly, "
                "collect their phone number to pull up their account, find out what class they want, "
                "and nail down their preferred day and time so we can find a great option for them."
            ),
            checklist=[
                guava.Say(
                    "Thanks for calling FlexFit Studio! I'm Jordan. I'd love to help you get into "
                    "a class today — let's find you something great."
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
                    key="class_type",
                    field_type="multiple_choice",
                    description=(
                        "Ask what type of class they'd like to book. "
                        "Map their answer to the closest option."
                    ),
                    choices=["yoga", "spin", "HIIT", "pilates", "barre", "boxing"],
                    required=True,
                ),
                guava.Field(
                    key="preferred_day",
                    field_type="text",
                    description=(
                        "Ask which day they'd like to attend — for example 'tomorrow', 'Monday', "
                        "or a specific date. Capture their answer as-is."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="preferred_time",
                    field_type="multiple_choice",
                    description=(
                        "Ask whether they prefer a morning, afternoon, or evening class. "
                        "Map their answer to the closest option."
                    ),
                    choices=["morning", "afternoon", "evening"],
                    required=True,
                ),
            ],
            on_complete=self.lookup_client,
        )

        self.accept_call()

    def lookup_client(self):
        phone = self.get_field("phone")
        class_type = self.get_field("class_type")
        preferred_day = self.get_field("preferred_day")
        preferred_time = self.get_field("preferred_time")

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
                        "Let the caller know we were unable to find an account matching the phone "
                        "number they provided. Ask them to double-check the number on file, or visit "
                        "the front desk to get their account set up. Thank them for calling FlexFit Studio."
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
                    "Apologize and let the caller know we're having trouble accessing the member "
                    "database right now. Ask them to try again in a few minutes or stop by the front desk."
                )
            )
            return

        self.check_credits()

    def check_credits(self):
        """Verify the member has active class credits before searching for classes."""
        class_type = self.get_field("class_type")

        try:
            token = get_staff_token()
            resp = requests.get(
                f"{BASE_URL}/client/clientservices",
                headers=get_headers(token),
                params={"ClientID": self.client_id},
                timeout=10,
            )
            resp.raise_for_status()
            services = resp.json().get("ClientServices", [])

            # Look for any active service with remaining count.
            active_credits = [
                s for s in services
                if s.get("Current") and (s.get("Count") is None or s.get("Count", 0) > 0)
            ]

            if not active_credits:
                logging.info("Client %s has no active class credits.", self.client_id)
                self.hangup(
                    final_instructions=(
                        f"Let {self.client_name} know that we weren't able to find any active class "
                        "credits on their account. They'll need to purchase a class pack or membership "
                        "before booking. Offer to transfer them to the front desk to take care of that "
                        "right now, or let them know they can also purchase online at flexfitstudio.com. "
                        "Thank them for calling FlexFit Studio."
                    )
                )
                return

            logging.info(
                "Client %s has %d active service(s).", self.client_id, len(active_credits)
            )

        except Exception as e:
            logging.error("Failed to fetch client services: %s", e)
            # Continue — don't block the member if the credits check fails.
            logging.warning("Proceeding to class search despite credits check failure.")

        self.search_classes()

    def search_classes(self):
        """Search for available classes matching the member's type and time preference."""
        class_type = self.get_field("class_type")
        preferred_day = self.get_field("preferred_day")
        preferred_time = self.get_field("preferred_time") or "morning"

        # Resolve preferred_day to an ISO date string.
        # We interpret simple words; anything else we treat as today + 1.
        today = datetime.now().date()
        day_lower = (preferred_day or "").strip().lower()
        if day_lower == "today":
            target_date = today
        elif day_lower == "tomorrow":
            target_date = today + timedelta(days=1)
        else:
            # Try to parse weekday names (e.g. "Monday").
            weekday_map = {
                "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
                "friday": 4, "saturday": 5, "sunday": 6,
            }
            if day_lower in weekday_map:
                target_weekday = weekday_map[day_lower]
                days_ahead = (target_weekday - today.weekday()) % 7 or 7
                target_date = today + timedelta(days=days_ahead)
            else:
                # Fall back to tomorrow as a safe default.
                target_date = today + timedelta(days=1)

        start_dt = datetime.combine(target_date, datetime.min.time())
        end_dt = start_dt + timedelta(hours=23, minutes=59)

        logging.info(
            "Searching for %s classes on %s (%s)", class_type, target_date, preferred_time
        )

        try:
            token = get_staff_token()
            resp = requests.get(
                f"{BASE_URL}/class/classes",
                headers=get_headers(token),
                params={
                    "StartDateTime": start_dt.isoformat(),
                    "EndDateTime": end_dt.isoformat(),
                    "_count": 20,
                },
                timeout=10,
            )
            resp.raise_for_status()
            all_classes = resp.json().get("Classes", [])

            # Filter by class name matching the requested type.
            type_lower = class_type.lower()
            matching = [
                c for c in all_classes
                if type_lower in (c.get("ClassDescription", {}).get("Name", "") or "").lower()
            ]

            # Filter by time-of-day preference.
            hour_start, hour_end = TIME_WINDOWS.get(preferred_time, (0, 24))
            time_filtered = []
            for c in matching:
                try:
                    class_hour = datetime.fromisoformat(
                        c["StartDateTime"].replace("Z", "+00:00")
                    ).hour
                    if hour_start <= class_hour < hour_end:
                        time_filtered.append(c)
                except (KeyError, ValueError):
                    pass

            # Fall back to any matching class if nothing in the preferred window.
            candidates = time_filtered or matching

            if not candidates:
                logging.info("No matching classes found for %s on %s.", class_type, target_date)
                self.hangup(
                    final_instructions=(
                        f"Let {self.client_name} know that we don't have any {class_type} classes "
                        f"available on {preferred_day} in the {preferred_time}. Suggest they check the "
                        "schedule online at flexfitstudio.com or call back to look at a different day. "
                        "Thank them for calling FlexFit Studio."
                    )
                )
                return

            self.selected_class = candidates[0]
            class_id = self.selected_class.get("Id")
            class_name = self.selected_class.get("ClassDescription", {}).get("Name", class_type)
            instructor = self.selected_class.get("Staff", {}).get("Name", "one of our instructors")
            start_raw = self.selected_class.get("StartDateTime", "")
            max_cap = self.selected_class.get("MaxCapacity", 0)
            total_booked = self.selected_class.get("TotalBooked", 0)
            spots_left = max(0, max_cap - total_booked)

            try:
                dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
                display_time = dt.strftime("%A, %B %-d at %-I:%M %p")
            except (ValueError, AttributeError):
                display_time = start_raw

            logging.info(
                "Found class: %s (ID: %s) on %s with %s — %d spot(s) left.",
                class_name, class_id, display_time, instructor, spots_left
            )

        except Exception as e:
            logging.error("Failed to search Mindbody classes: %s", e)
            self.hangup(
                final_instructions=(
                    "Apologize and let the caller know we're having trouble loading the class "
                    "schedule right now. Ask them to try again shortly or check the schedule online."
                )
            )
            return

        # Present the class and ask for confirmation.
        self.set_task(
            objective=(
                f"Present the found {class_type} class to {self.client_name} and confirm they "
                "want to book it."
            ),
            checklist=[
                guava.Say(
                    f"Great news, {self.client_name}! I found a {class_name} class on {display_time} "
                    f"with {instructor}. There {'is' if spots_left == 1 else 'are'} "
                    f"{spots_left} spot{'s' if spots_left != 1 else ''} left. "
                    "Would you like me to go ahead and book that for you?"
                ),
                guava.Field(
                    key="confirm_booking",
                    field_type="multiple_choice",
                    description=(
                        "Ask the member to confirm whether they want to book this class. "
                        "Map their answer to 'yes, book it' or 'no, skip it'."
                    ),
                    choices=["yes, book it", "no, skip it"],
                    required=True,
                ),
            ],
            on_complete=self.finalize_booking,
        )

    def finalize_booking(self):
        confirm = self.get_field("confirm_booking")
        class_type = self.get_field("class_type")

        if confirm != "yes, book it":
            self.hangup(
                final_instructions=(
                    f"No problem — let {self.client_name} know no class was booked. "
                    "Encourage them to check the full schedule at flexfitstudio.com to find a time "
                    "that works better. Thank them for calling FlexFit Studio and wish them a great day."
                )
            )
            return

        class_id = self.selected_class.get("Id")
        class_name = self.selected_class.get("ClassDescription", {}).get("Name", class_type)
        start_raw = self.selected_class.get("StartDateTime", "")

        try:
            dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
            display_time = dt.strftime("%A, %B %-d at %-I:%M %p")
        except (ValueError, AttributeError):
            display_time = start_raw

        try:
            token = get_staff_token()
            resp = requests.post(
                f"{BASE_URL}/class/addenrollment",
                headers=get_headers(token),
                json={
                    "ClientId": self.client_id,
                    "ClassId": class_id,
                    "Test": False,
                },
                timeout=10,
            )
            resp.raise_for_status()
            logging.info(
                "Successfully enrolled client %s in class %s (%s).",
                self.client_id, class_id, class_name,
            )
        except Exception as e:
            logging.error("Failed to enroll client in class: %s", e)
            self.hangup(
                final_instructions=(
                    f"Apologize to {self.client_name} and let them know we ran into a problem "
                    "completing the booking. Ask them to try booking online at flexfitstudio.com "
                    "or call back in a few minutes. Thank them for calling."
                )
            )
            return

        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "Jordan",
            "organization": "FlexFit Studio",
            "use_case": "class_booking",
            "client_id": self.client_id,
            "client_name": self.client_name,
            "class_id": class_id,
            "class_name": class_name,
            "class_start": start_raw,
            "fields": {
                "phone": self.get_field("phone"),
                "class_type": self.get_field("class_type"),
                "preferred_day": self.get_field("preferred_day"),
                "preferred_time": self.get_field("preferred_time"),
                "confirm_booking": confirm,
            },
        }
        print(json.dumps(results, indent=2))
        logging.info("Class booking result saved.")

        self.hangup(
            final_instructions=(
                f"Confirm to {self.client_name} that they're all set — their spot in the "
                f"{class_name} class on {display_time} has been booked. Remind them to arrive "
                "5–10 minutes early and to bring water and a towel. Thank them for calling "
                "FlexFit Studio and wish them a great workout!"
            )
        )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=ClassBookingController,
    )
