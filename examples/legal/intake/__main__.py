import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
from guava import logging_utils

agent = guava.Agent(
    name="Jordan",
    organization="Hargrove & Associates Law Firm",
    purpose=(
        "to conduct an initial client intake, gather information about the "
        "prospective client's legal matter, and determine whether there are "
        "any conflicts of interest before connecting them with an attorney"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "intake",
        objective=(
            "Collect the prospective client's contact information and a clear "
            "description of their legal matter so the firm can perform a conflict "
            "check and have an attorney follow up within one business day. Maintain "
            "a professional and empathetic tone throughout. Do not provide any legal "
            "advice or opinions."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Hargrove and Associates. My name is Jordan "
                "and I will be collecting some initial information about your matter "
                "today. I want to let you know that nothing discussed during this "
                "call constitutes legal advice, and an attorney will review your "
                "information and reach out to you directly. This should only take "
                "a few minutes."
            ),
            guava.Field(
                key="caller_name",
                description="The caller's full legal name",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="caller_phone",
                description="The best phone number to reach the caller",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="matter_type",
                description=(
                    "The general category of legal matter. Ask the caller which "
                    "best describes their situation: personal injury, family law, "
                    "criminal defense, business law, estate planning, or other"
                ),
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="brief_matter_description",
                description=(
                    "A concise description of the legal matter in the caller's own "
                    "words — what happened and what they need help with"
                ),
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="adverse_parties_names",
                description=(
                    "The full names of any opposing or adverse parties involved in "
                    "the matter — for example, the other driver, an opposing spouse, "
                    "a business counterparty, or a prosecuting authority. This is "
                    "needed to check for conflicts of interest."
                ),
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="desired_outcome",
                description=(
                    "What the caller is hoping to achieve or what outcome they are "
                    "looking for from legal representation"
                ),
                field_type="text",
                required=False,
            ),
            guava.Field(
                key="how_did_you_hear_about_us",
                description="How the caller heard about or was referred to Hargrove and Associates",
                field_type="text",
                required=False,
            ),
            guava.Field(
                key="urgency_level",
                description=(
                    "The urgency of the matter. Ask whether their situation is "
                    "urgent — for example involving an upcoming court date or "
                    "statute of limitations deadline — standard, or exploratory "
                    "at this stage"
                ),
                field_type="text",
                required=True,
            ),
        ],
    )


@agent.on_task_complete("intake")
def on_done(call: guava.Call) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "call_type": "inbound_client_intake",
        "fields": {
            "caller_name": call.get_field("caller_name"),
            "caller_phone": call.get_field("caller_phone"),
            "matter_type": call.get_field("matter_type"),
            "brief_matter_description": call.get_field("brief_matter_description"),
            "adverse_parties_names": call.get_field("adverse_parties_names"),
            "desired_outcome": call.get_field("desired_outcome"),
            "how_did_you_hear_about_us": call.get_field("how_did_you_hear_about_us"),
            "urgency_level": call.get_field("urgency_level"),
        },
    }
    print(json.dumps(results, indent=2))
    logging.info("Client intake results saved.")
    call.hangup(
        final_instructions=(
            "Thank the caller by name for their time. Confirm that their information "
            "has been received and that an attorney at Hargrove and Associates will "
            "review the details and call them back at the number they provided within "
            "one business day. If their matter is urgent, acknowledge that and assure "
            "them it will be flagged accordingly. Remind them once more that nothing "
            "discussed during this call constitutes legal advice. Wish them well and "
            "say goodbye professionally."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
