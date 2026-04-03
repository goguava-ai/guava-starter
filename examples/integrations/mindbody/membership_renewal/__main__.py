import guava
import os
import logging
import argparse
import requests

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


def fetch_client_account(client_id: str) -> dict:
    """Return the client's account summary including credits and membership status."""
    resp = requests.get(
        f"{BASE_URL}/sale/clientaccount",
        headers=HEADERS,
        params={"clientId": client_id},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_client_details(client_id: str) -> dict:
    """Return client profile information."""
    resp = requests.get(
        f"{BASE_URL}/client/clients",
        headers=HEADERS,
        params={"clientIds": client_id},
        timeout=10,
    )
    resp.raise_for_status()
    clients = resp.json().get("Clients", [])
    return clients[0] if clients else {}


def send_renewal_followup_email(client_id: str):
    """Send an automated follow-up email about membership renewal."""
    resp = requests.post(
        f"{BASE_URL}/client/sendautoemail",
        headers=HEADERS,
        json={
            "ClientId": client_id,
            "AutoEmailTypeId": 5,  # Membership expiration follow-up type
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


class MembershipRenewalController(guava.CallController):
    def __init__(self, client_name: str, client_id: str, expiry_date: str,
                 membership_name: str):
        super().__init__()
        self.client_name = client_name
        self.client_id = client_id
        self.expiry_date = expiry_date
        self.membership_name = membership_name

        # Pre-fetch account status to personalize the conversation.
        try:
            self.account = fetch_client_account(client_id)
            self.client_details = fetch_client_details(client_id)
        except Exception as e:
            logging.error("Failed to pre-fetch client account for %s: %s", client_id, e)
            self.account = None
            self.client_details = {}

        self.set_persona(
            organization_name="Harmony Wellness Center",
            agent_name="Morgan",
            agent_purpose="to help members manage and renew their memberships",
        )

        self.reach_person(
            contact_full_name=self.client_name,
            on_success=self.begin_call,
            on_failure=self.recipient_unavailable,
        )

    def begin_call(self):
        # Determine remaining credits to personalize the message.
        remaining_credits = 0
        if self.account:
            product_services = self.account.get("ProductServices", [])
            if product_services:
                remaining_credits = sum(
                    ps.get("Remaining", 0) for ps in product_services
                )

        credits_note = (
            f" You still have {remaining_credits} session credit{'s' if remaining_credits != 1 else ''} remaining."
            if remaining_credits > 0
            else ""
        )

        self.set_task(
            objective=(
                f"Reach {self.client_name} to discuss renewing their {self.membership_name} "
                f"membership expiring on {self.expiry_date} and capture their renewal interest."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.client_name}, this is Morgan calling from Harmony Wellness Center. "
                    f"I'm reaching out because your {self.membership_name} membership is coming up "
                    f"for renewal on {self.expiry_date}.{credits_note} "
                    "I wanted to connect with you personally to make sure you're taken care of."
                ),
                guava.Field(
                    key="still_interested",
                    field_type="multiple_choice",
                    description=(
                        f"Ask {self.client_name} if they are interested in continuing their membership "
                        "with Harmony Wellness Center."
                    ),
                    choices=["yes", "no", "not sure yet"],
                    required=True,
                ),
                guava.Field(
                    key="renewal_plan",
                    field_type="multiple_choice",
                    description=(
                        "If they are interested, ask which renewal option they prefer. "
                        "Mention the options are monthly, quarterly (saves 10%), or annual (saves 20%). "
                        "Only ask this if the previous answer was 'yes'."
                    ),
                    choices=["monthly", "quarterly", "annual"],
                    required=False,
                ),
                guava.Field(
                    key="hesitation_reason",
                    field_type="text",
                    description=(
                        "If they said 'no' or 'not sure yet', gently ask what is holding them back — "
                        "cost, scheduling, or something else. This helps us serve them better."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="best_callback_time",
                    field_type="text",
                    description=(
                        "If they need more time to decide, ask for the best time for a team member "
                        "to follow up with them."
                    ),
                    required=False,
                ),
            ],
            on_complete=self.handle_outcome,
        )

    def handle_outcome(self):
        interest = self.get_field("still_interested")
        renewal_plan = self.get_field("renewal_plan")
        hesitation = self.get_field("hesitation_reason")
        callback_time = self.get_field("best_callback_time")

        logging.info(
            "Renewal outcome — client=%s interest=%s plan=%s hesitation=%s callback=%s",
            self.client_id, interest, renewal_plan, hesitation, callback_time,
        )

        if interest == "yes" and renewal_plan:
            # Send follow-up email with renewal details.
            try:
                send_renewal_followup_email(self.client_id)
                logging.info("Sent renewal follow-up email to client %s", self.client_id)
            except Exception as e:
                logging.error("Failed to send renewal email to %s: %s", self.client_id, e)

            plan_savings = {
                "monthly": "no additional discount",
                "quarterly": "10% savings",
                "annual": "20% savings",
            }
            savings_msg = plan_savings.get(renewal_plan, "")

            self.hangup(
                final_instructions=(
                    f"Thank {self.client_name} enthusiastically for choosing to renew their membership. "
                    f"Confirm they selected the {renewal_plan} plan ({savings_msg}). "
                    "Let them know a team member will process the renewal and send a confirmation email shortly. "
                    "Tell them we're excited to keep supporting their wellness journey. Be warm and celebratory."
                )
            )

        elif interest == "not sure yet" or (interest == "no" and callback_time):
            try:
                send_renewal_followup_email(self.client_id)
            except Exception as e:
                logging.error("Failed to send follow-up email: %s", e)

            self.hangup(
                final_instructions=(
                    f"Thank {self.client_name} for their time and let them know there is absolutely "
                    "no pressure. Tell them a team member will follow up at the time they requested "
                    "and that a renewal information email is on its way. "
                    "Remind them their membership is active until the expiry date. Be understanding and warm."
                )
            )

        else:
            self.hangup(
                final_instructions=(
                    f"Thank {self.client_name} genuinely for being a member of Harmony Wellness Center. "
                    "Let them know the door is always open if they change their mind and invite them "
                    "to call or visit anytime. Wish them well on their wellness journey. Be sincere and kind."
                )
            )

    def recipient_unavailable(self):
        self.hangup(
            final_instructions=(
                f"Leave a brief, friendly voicemail for {self.client_name} letting them know "
                f"their {self.membership_name} membership at Harmony Wellness Center is expiring "
                f"on {self.expiry_date}. Ask them to call us back or visit our website to renew. "
                "Keep it under 30 seconds, be warm, and leave the studio phone number as a callback."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Call a client with an expiring membership to offer renewal options."
    )
    parser.add_argument("phone", help="Client phone number in E.164 format, e.g. +13105550142")
    parser.add_argument("--client-id", required=True, help="Mindbody client ID")
    parser.add_argument("--name", required=True, help="Client full name")
    parser.add_argument(
        "--expiry-date",
        required=True,
        help="Membership expiry date in human-readable format, e.g. 'April 15th'",
    )
    parser.add_argument(
        "--membership-name",
        required=True,
        help="Name of the membership, e.g. 'Unlimited Monthly'",
    )
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=MembershipRenewalController(
            client_name=args.name,
            client_id=args.client_id,
            expiry_date=args.expiry_date,
            membership_name=args.membership_name,
        ),
    )
