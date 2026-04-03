import guava
import os
import logging
import requests

logging.basicConfig(level=logging.INFO)

SITE = os.environ["CHARGEBEE_SITE"]
BASE_URL = f"https://{SITE}.chargebee.com/api/v2"
AUTH = (os.environ["CHARGEBEE_API_KEY"], "")


def get_subscription(subscription_id: str) -> dict | None:
    resp = requests.get(f"{BASE_URL}/subscriptions/{subscription_id}", auth=AUTH, timeout=10)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json().get("subscription")


def list_plans() -> list:
    resp = requests.get(f"{BASE_URL}/plans", auth=AUTH, timeout=10)
    if not resp.ok:
        return []
    return [entry.get("plan") for entry in resp.json().get("list", []) if entry.get("plan")]


def change_plan(subscription_id: str, new_plan_id: str) -> dict | None:
    resp = requests.post(
        f"{BASE_URL}/subscriptions/{subscription_id}",
        auth=AUTH,
        data={"plan_id": new_plan_id, "replace_addon_list": "false"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("subscription")


def format_amount(cents: int, currency: str = "USD") -> str:
    return f"${cents / 100:,.2f} {currency.upper()}"


class PlanUpgradeController(guava.CallController):
    def __init__(self):
        super().__init__()
        self.plans = []

        try:
            self.plans = list_plans()
            logging.info("Loaded %d Chargebee plans.", len(self.plans))
        except Exception as e:
            logging.warning("Could not pre-load plans: %s", e)

        self.set_persona(
            organization_name="Vault",
            agent_name="Riley",
            agent_purpose="to help Vault customers upgrade their subscription plan",
        )

        plan_names = [p.get("name", "") for p in self.plans if p.get("name")]
        plan_hint = f"Available plans: {', '.join(plan_names)}." if plan_names else ""

        self.set_task(
            objective=(
                "A customer wants to upgrade their Vault subscription. "
                "Verify their subscription and help them choose a higher-tier plan."
            ),
            checklist=[
                guava.Say(
                    "Thanks for calling Vault. This is Riley. "
                    "I'd love to help you upgrade your subscription today."
                ),
                guava.Field(
                    key="subscription_id",
                    field_type="text",
                    description="Ask for their subscription ID from their billing email.",
                    required=True,
                ),
                guava.Field(
                    key="desired_plan",
                    field_type="text",
                    description=f"Ask which plan they'd like to upgrade to. {plan_hint}",
                    required=True,
                ),
                guava.Field(
                    key="confirmed",
                    field_type="multiple_choice",
                    description=(
                        "Confirm they'd like to make the upgrade. Let them know the new billing "
                        "amount takes effect at the next renewal unless prorated."
                    ),
                    choices=["yes, upgrade my plan", "no, keep my current plan"],
                    required=True,
                ),
            ],
            on_complete=self.process_upgrade,
        )

        self.accept_call()

    def process_upgrade(self):
        subscription_id = (self.get_field("subscription_id") or "").strip()
        desired_plan = (self.get_field("desired_plan") or "").strip().lower()
        confirmed = self.get_field("confirmed") or ""

        if "keep" in confirmed or "no" in confirmed:
            self.hangup(
                final_instructions=(
                    "Let the caller know their plan has not been changed. "
                    "Thank them for considering an upgrade and let them know we're here when they're ready. "
                    "Wish them a great day."
                )
            )
            return

        # Resolve plan ID from desired name
        matched_plan = None
        for plan in self.plans:
            if desired_plan in (plan.get("name", "")).lower() or desired_plan in (plan.get("id", "")).lower():
                matched_plan = plan
                break

        if not matched_plan:
            self.hangup(
                final_instructions=(
                    f"Let the caller know we couldn't find a plan matching '{desired_plan}'. "
                    "Ask them to call back or check the Vault website for available plans. "
                    "Be apologetic and helpful."
                )
            )
            return

        new_plan_id = matched_plan.get("id", "")
        new_plan_name = matched_plan.get("name", new_plan_id)
        new_plan_price = matched_plan.get("price", 0)
        currency = matched_plan.get("currency_code", "USD")
        period_unit = matched_plan.get("period_unit", "month")
        price_str = format_amount(new_plan_price, currency) if new_plan_price else ""

        logging.info("Upgrading subscription %s to plan %s", subscription_id, new_plan_id)

        upgraded = None
        try:
            upgraded = change_plan(subscription_id, new_plan_id)
            logging.info("Plan upgraded: %s", upgraded.get("plan_id") if upgraded else None)
        except Exception as e:
            logging.error("Plan change failed: %s", e)

        if upgraded:
            self.hangup(
                final_instructions=(
                    f"Let the caller know their Vault subscription has been upgraded to the {new_plan_name} plan"
                    + (f" at {price_str}/{period_unit}" if price_str else "")
                    + ". The change takes effect immediately. "
                    "Thank them for upgrading and let them know the team is here if they have any questions. "
                    "Wish them a great day."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    "Apologize — the plan upgrade couldn't be processed automatically. "
                    "Let the caller know our team will complete the upgrade by end of day and they'll "
                    "receive a confirmation email. Thank them for their patience."
                )
            )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=PlanUpgradeController,
    )
