import guava
import os
import logging
from guava import logging_utils
from datetime import datetime, timezone
from pymongo import MongoClient


_client = MongoClient(os.environ["MONGODB_URI"])
_db = _client[os.environ["MONGODB_DATABASE"]]
customers = _db["customers"]


def find_customer_by_email(email: str) -> dict | None:
    return customers.find_one({"email": email})


def update_preferences(customer_id, prefs: dict) -> None:
    """Updates the preferences subdocument and records the change timestamp."""
    customers.update_one(
        {"_id": customer_id},
        {
            "$set": {
                **{f"preferences.{k}": v for k, v in prefs.items()},
                "preferences.updated_at": datetime.now(tz=timezone.utc),
            }
        },
    )


class PreferenceUpdateController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Vantage",
            agent_name="Sam",
            agent_purpose=(
                "to help Vantage customers update their notification and "
                "communication preferences"
            ),
        )

        self.set_task(
            objective=(
                "A customer has called to update how they hear from Vantage. "
                "Verify their identity, then walk through each preference and apply the changes."
            ),
            checklist=[
                guava.Say(
                    "Thanks for calling Vantage. I'm Sam. "
                    "I can help you update your notification preferences. "
                    "Let me pull up your account."
                ),
                guava.Field(
                    key="email",
                    field_type="text",
                    description="Ask for their email address on file.",
                    required=True,
                ),
                guava.Field(
                    key="marketing_emails",
                    field_type="multiple_choice",
                    description=(
                        "Ask if they'd like to receive marketing and product update emails from Vantage."
                    ),
                    choices=["yes", "no", "no change"],
                    required=True,
                ),
                guava.Field(
                    key="sms_notifications",
                    field_type="multiple_choice",
                    description="Ask if they'd like to receive SMS notifications for account alerts.",
                    choices=["yes", "no", "no change"],
                    required=True,
                ),
                guava.Field(
                    key="weekly_digest",
                    field_type="multiple_choice",
                    description=(
                        "Ask if they'd like to receive a weekly usage and insights digest by email."
                    ),
                    choices=["yes", "no", "no change"],
                    required=True,
                ),
                guava.Field(
                    key="contact_frequency",
                    field_type="multiple_choice",
                    description=(
                        "Ask how often they'd be comfortable hearing from our team proactively."
                    ),
                    choices=["as needed", "monthly", "quarterly", "never"],
                    required=False,
                ),
            ],
            on_complete=self.apply_preferences,
        )

        self.accept_call()

    def apply_preferences(self):
        email = (self.get_field("email") or "").strip().lower()

        logging.info("Looking up customer for preference update: %s", email)

        try:
            customer = find_customer_by_email(email)
        except Exception as e:
            logging.error("MongoDB lookup failed for %s: %s", email, e)
            customer = None

        if not customer:
            self.hangup(
                final_instructions=(
                    "Let the caller know you couldn't find an account with that email address. "
                    "Ask them to double-check or offer to connect them with a support agent."
                )
            )
            return

        name = customer.get("name") or "there"
        updates = {}

        for key, pref_key in [
            ("marketing_emails", "marketing_emails"),
            ("sms_notifications", "sms_notifications"),
            ("weekly_digest", "weekly_digest"),
        ]:
            value = self.get_field(key) or "no change"
            if value in ("yes", "no"):
                updates[pref_key] = value == "yes"

        contact_freq = self.get_field("contact_frequency") or ""
        if contact_freq and contact_freq != "no change":
            updates["contact_frequency"] = contact_freq

        if not updates:
            self.hangup(
                final_instructions=(
                    f"Let {name} know that no changes were made since they selected 'no change' "
                    "for all preferences."
                )
            )
            return

        logging.info(
            "Updating preferences for customer %s: %s", customer["_id"], updates
        )

        try:
            update_preferences(customer["_id"], updates)
            changed = ", ".join(
                k.replace("_", " ") + f" → {'on' if v is True else 'off' if v is False else v}"
                for k, v in updates.items()
            )
            logging.info("Preferences updated for %s", email)
            self.hangup(
                final_instructions=(
                    f"Let {name} know their preferences have been updated successfully. "
                    f"Confirm the changes: {changed}. "
                    "Let them know changes take effect immediately. "
                    "Thank them for calling and wish them a great day."
                )
            )
        except Exception as e:
            logging.error("Failed to update preferences for %s: %s", email, e)
            self.hangup(
                final_instructions=(
                    f"Apologize to {name} for a technical issue. Let them know their preference "
                    "changes have been noted and a team member will apply them manually and "
                    "confirm by email within one business day."
                )
            )


if __name__ == "__main__":
    logging_utils.configure_logging()
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=PreferenceUpdateController,
    )
