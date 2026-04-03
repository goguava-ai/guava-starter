import guava
import os
import logging
import pymysql
import pymysql.cursors

logging.basicConfig(level=logging.INFO)

# Points required to reach each tier and the perks associated with them.
TIERS = {
    "bronze": {"min": 0, "next": 500, "next_name": "silver", "perk": "5% off all purchases"},
    "silver": {"min": 500, "next": 2000, "next_name": "gold", "perk": "10% off + free shipping"},
    "gold": {"min": 2000, "next": 5000, "next_name": "platinum", "perk": "15% off + priority service"},
    "platinum": {"min": 5000, "next": None, "next_name": None, "perk": "20% off + free gear checks"},
}


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


def get_customer_by_email(email: str) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, name, email, phone, loyalty_points, loyalty_tier
                FROM customers
                WHERE email = %s
                LIMIT 1
                """,
                (email,),
            )
            return cursor.fetchone()


def get_customer_by_phone(phone: str) -> dict | None:
    # Normalize to digits only for a flexible match
    digits = "".join(c for c in phone if c.isdigit())
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, name, email, phone, loyalty_points, loyalty_tier
                FROM customers
                WHERE REGEXP_REPLACE(phone, '[^0-9]', '') = %s
                LIMIT 1
                """,
                (digits,),
            )
            return cursor.fetchone()


class LoyaltyPointsController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Peak Outdoors",
            agent_name="Sam",
            agent_purpose=(
                "to help Peak Outdoors loyalty members check their points balance and tier status"
            ),
        )

        self.set_task(
            objective=(
                "A loyalty member has called to check their points balance. "
                "Look them up by email or phone, then share their current points, "
                "tier, perks, and how many points they need for the next tier."
            ),
            checklist=[
                guava.Say(
                    "Thanks for calling Peak Outdoors. I'm Sam. "
                    "I can pull up your loyalty account right now."
                ),
                guava.Field(
                    key="lookup_method",
                    field_type="multiple_choice",
                    description="Ask if they'd prefer to look up their account by email or phone number.",
                    choices=["email", "phone number"],
                    required=True,
                ),
                guava.Field(
                    key="lookup_value",
                    field_type="text",
                    description="Ask for their email address or phone number, based on their choice.",
                    required=True,
                ),
            ],
            on_complete=self.look_up_loyalty,
        )

        self.accept_call()

    def look_up_loyalty(self):
        method = self.get_field("lookup_method") or "email"
        value = (self.get_field("lookup_value") or "").strip()

        logging.info("Looking up loyalty account by %s: %s", method, value)

        try:
            customer = (
                get_customer_by_email(value)
                if "email" in method
                else get_customer_by_phone(value)
            )
        except Exception as e:
            logging.error("Database error looking up customer: %s", e)
            customer = None

        if not customer:
            self.hangup(
                final_instructions=(
                    f"Let the caller know you couldn't find a loyalty account matching "
                    f"the {method} they provided. Ask them to double-check or offer to connect "
                    "them with a team member who can look it up in-store."
                )
            )
            return

        name = customer.get("name") or "there"
        points = int(customer.get("loyalty_points") or 0)
        tier = (customer.get("loyalty_tier") or "bronze").lower()

        tier_info = TIERS.get(tier, TIERS["bronze"])
        perk = tier_info["perk"]
        next_tier = tier_info["next_name"]
        points_to_next = (
            tier_info["next"] - points
            if tier_info["next"] is not None and points < tier_info["next"]
            else 0
        )

        logging.info(
            "Loyalty account found: %s, tier=%s, points=%d", name, tier, points
        )

        next_tier_note = (
            f"They need {points_to_next:,} more points to reach {next_tier} status. "
            if next_tier and points_to_next > 0
            else "They are at the highest tier — Platinum. "
        )

        self.hangup(
            final_instructions=(
                f"Greet {name} by name. "
                f"Their current loyalty points balance is {points:,} points. "
                f"They are a {tier.title()} member, which comes with: {perk}. "
                + next_tier_note
                + "Let them know they earn 1 point for every dollar spent. "
                "Thank them for being a Peak Outdoors member."
            )
        )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=LoyaltyPointsController,
    )
