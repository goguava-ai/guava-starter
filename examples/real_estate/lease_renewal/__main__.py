import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
from guava import logging_utils

agent = guava.Agent(
    name="Casey",
    organization="Pinnacle Property Management",
    purpose=(
        "reach out to tenants ahead of their lease expiration to gauge "
        "renewal interest and collect updated contact and income information "
        "so the leasing team can prepare renewal agreements efficiently"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("contact_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")
    unit_address = call.get_variable("unit_address")
    expiration_date = call.get_variable("expiration_date")

    if outcome == "unavailable":
        logging.warning(
            "Could not reach %s at %s for lease renewal outreach.",
            contact_name,
            unit_address,
        )
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "vertical": "real_estate",
            "use_case": "lease_renewal",
            "contact_name": contact_name,
            "unit_address": unit_address,
            "lease_expiration": expiration_date,
            "status": "recipient_unavailable",
        }
        print(json.dumps(results, indent=2))
        call.hangup(
            final_instructions=(
                f"Leave a brief, professional voicemail for {contact_name}. "
                "Introduce yourself as Casey from Pinnacle Property Management and mention "
                f"that you are calling about their upcoming lease renewal at {unit_address} "
                f"expiring {expiration_date}. Ask them to call back at their earliest "
                "convenience or watch for an email from the leasing team. Keep the message "
                "friendly and under 30 seconds."
            )
        )
    elif outcome == "available":
        call.set_task(
            "lease_renewal_survey",
            objective=(
                f"You are calling {contact_name}, a current tenant at "
                f"{unit_address}, whose lease expires {expiration_date}. "
                "Be warm, professional, and low-pressure. Let them know this is a "
                "courtesy call to understand their intentions and make the renewal "
                "process as smooth as possible if they choose to stay. "
                "Reassure them that there is no obligation and their feedback is appreciated."
            ),
            checklist=[
                guava.Say(
                    f"Hi {contact_name}, this is Casey calling from Pinnacle Property "
                    f"Management regarding your lease at {unit_address}, which is coming "
                    f"up for renewal {expiration_date}. I just have a few quick questions "
                    f"to help us plan ahead — this should only take a couple of minutes."
                ),
                guava.Field(
                    key="renewal_intent",
                    description=(
                        "Are you planning to renew your lease, or are you considering moving? "
                        "You can say yes, no, or undecided if you haven't made up your mind yet."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="preferred_lease_term",
                    description=(
                        "If you do plan to renew, do you have a preference for the lease term? "
                        "For example, a 6-month, 12-month, or month-to-month arrangement?"
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="income_change_since_last_lease",
                    description=(
                        "Has your household income changed significantly since you signed "
                        "your last lease? We may need updated income verification as part "
                        "of the renewal process."
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="updated_phone",
                    description=(
                        "Is the phone number we have on file still the best one to reach you? "
                        "If not, what is your current phone number?"
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="updated_email",
                    description=(
                        "Do you have an updated email address you'd like us to use "
                        "for lease documents and communications?"
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="maintenance_concerns_before_renewal",
                    description=(
                        "Before you commit to renewing, are there any outstanding maintenance "
                        "issues or concerns about the unit you'd like addressed?"
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("lease_renewal_survey")
def on_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    unit_address = call.get_variable("unit_address")
    expiration_date = call.get_variable("expiration_date")
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "vertical": "real_estate",
        "use_case": "lease_renewal",
        "contact_name": contact_name,
        "unit_address": unit_address,
        "lease_expiration": expiration_date,
        "fields": {
            "renewal_intent": call.get_field("renewal_intent"),
            "preferred_lease_term": call.get_field("preferred_lease_term"),
            "income_change_since_last_lease": call.get_field("income_change_since_last_lease"),
            "updated_phone": call.get_field("updated_phone"),
            "updated_email": call.get_field("updated_email"),
            "maintenance_concerns_before_renewal": call.get_field(
                "maintenance_concerns_before_renewal"
            ),
        },
    }
    print(json.dumps(results, indent=2))
    logging.info("Lease renewal survey results captured: %s", results)
    call.hangup(
        final_instructions=(
            f"Thank {contact_name} for their time and for being a valued tenant "
            f"at Pinnacle Property Management. Let them know that their leasing "
            "specialist will follow up with them by email within 3 to 5 business days "
            "with renewal options and next steps. If they indicated maintenance concerns, "
            "acknowledge those specifically and assure them the team will look into it. "
            "Wish them a great day and close warmly."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(description="Lease renewal outbound call to a tenant.")
    parser.add_argument("phone", help="The tenant's phone number to call.")
    parser.add_argument("--name", required=True, help="Full name of the tenant to reach.")
    parser.add_argument("--unit", required=True, help="Unit address of the tenant's rental.")
    parser.add_argument(
        "--expiration-date",
        default="in 60 days",
        help="Lease expiration date or description (e.g., 'on April 30th' or 'in 60 days').",
    )
    args = parser.parse_args()

    logging.info(
        "Initiating lease renewal call to %s (%s) for unit %s, expiring %s.",
        args.name,
        args.phone,
        args.unit,
        args.expiration_date,
    )

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "contact_name": args.name,
            "unit_address": args.unit,
            "expiration_date": args.expiration_date,
        },
    )
