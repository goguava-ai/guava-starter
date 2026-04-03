import guava
import os
import logging
import requests

logging.basicConfig(level=logging.INFO)

BASE_URL = os.environ.get("SQUARE_BASE_URL", "https://connect.squareupsandbox.com")
SQUARE_VERSION = "2024-01-18"


def get_headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ['SQUARE_ACCESS_TOKEN']}",
        "Square-Version": SQUARE_VERSION,
        "Content-Type": "application/json",
    }


def search_loyalty_account(phone: str) -> dict | None:
    """Searches for a loyalty account by phone number."""
    resp = requests.post(
        f"{BASE_URL}/v2/loyalty/accounts/search",
        headers=get_headers(),
        json={"query": {"mappings": [{"type": "PHONE", "value": phone}]}},
        timeout=10,
    )
    if not resp.ok:
        return None
    accounts = resp.json().get("loyalty_accounts", [])
    return accounts[0] if accounts else None


def get_loyalty_program() -> dict | None:
    """Fetches the loyalty program details to understand reward tiers."""
    resp = requests.get(
        f"{BASE_URL}/v2/loyalty/programs/main",
        headers=get_headers(),
        timeout=10,
    )
    if not resp.ok:
        return None
    return resp.json().get("program")


class LoyaltyRewardsController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Harbor Market",
            agent_name="Drew",
            agent_purpose="to help Harbor Market customers check their loyalty points and rewards status",
        )

        self.set_task(
            objective=(
                "A customer has called to check their loyalty points balance and reward status. "
                "Verify their phone number and look up their account."
            ),
            checklist=[
                guava.Say(
                    "Thanks for calling Harbor Market. This is Drew. "
                    "I can check your loyalty rewards account today."
                ),
                guava.Field(
                    key="phone",
                    field_type="text",
                    description=(
                        "Ask for the phone number linked to their Harbor Market loyalty account. "
                        "Capture including country code if given."
                    ),
                    required=True,
                ),
            ],
            on_complete=self.lookup_loyalty,
        )

        self.accept_call()

    def lookup_loyalty(self):
        phone = (self.get_field("phone") or "").strip()
        # Normalize phone: remove spaces and dashes, ensure +1 prefix for US
        clean_phone = "".join(c for c in phone if c.isdigit() or c == "+")
        if clean_phone and not clean_phone.startswith("+"):
            clean_phone = "+1" + clean_phone

        logging.info("Searching loyalty account for phone: %s", clean_phone)

        account = None
        program = None
        try:
            account = search_loyalty_account(clean_phone)
            if account:
                program = get_loyalty_program()
        except Exception as e:
            logging.error("Loyalty lookup failed: %s", e)

        if not account:
            self.hangup(
                final_instructions=(
                    f"Let the caller know we couldn't find a loyalty account linked to {phone}. "
                    "Ask them to make sure they signed up in-store or to visit Harbor Market to enroll. "
                    "Be friendly and helpful."
                )
            )
            return

        balance = account.get("balance", 0)
        lifetime_points = account.get("lifetime_points", 0)
        rewards = account.get("reward_tier_ids_ordered", [])

        # Find next reward tier threshold
        next_threshold = None
        next_reward_name = ""
        if program:
            tiers = program.get("reward_tiers", [])
            for tier in sorted(tiers, key=lambda t: t.get("points_requirement", 0)):
                threshold = tier.get("points_requirement", 0)
                if threshold > balance:
                    next_threshold = threshold
                    next_reward_name = tier.get("name", "")
                    break

        points_to_next = (next_threshold - balance) if next_threshold else None

        logging.info(
            "Loyalty account found: balance=%d, lifetime=%d, rewards=%s",
            balance, lifetime_points, len(rewards),
        )

        self.hangup(
            final_instructions=(
                f"Let the caller know their Harbor Market loyalty account has {balance} points. "
                f"Their lifetime total is {lifetime_points} points. "
                + (f"They have {len(rewards)} reward(s) available to redeem. " if rewards else "")
                + (f"They need {points_to_next} more points to reach the next reward: '{next_reward_name}'. " if points_to_next and next_reward_name else "")
                + "Remind them they earn points on every purchase at Harbor Market. "
                "To redeem rewards, they can show their phone number at checkout. "
                "Wish them a great day."
            )
        )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=LoyaltyRewardsController,
    )
