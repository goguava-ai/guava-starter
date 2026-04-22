import json
import logging
import os
from datetime import datetime, timezone

import guava
from guava import logging_utils

agent = guava.Agent(
    name="Jordan",
    organization="Keystone Property & Casualty",
    purpose=(
        "to assist policyholders with filing a First Notice of Loss "
        "and collecting the details needed to open a new insurance claim"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "fnol",
        objective=(
            "Collect all required information to open a First Notice of Loss (FNOL) "
            "claim on behalf of the policyholder. Gather their policy number, personal "
            "details, the date and nature of the loss, where it occurred, whether any "
            "injuries were involved, and a good callback number. Assure the caller that "
            "a licensed adjuster will follow up and that a claim number will be emailed "
            "to them promptly."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Keystone Property & Casualty. I'm sorry to hear "
                "you're experiencing a loss. I'm going to collect some information to get "
                "your claim started right away."
            ),
            guava.Field(
                key="policy_number",
                description="The policyholder's policy number",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="policyholder_name",
                description="The full legal name of the policyholder",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="loss_date",
                description="The date the loss or damage occurred",
                field_type="date",
                required=True,
            ),
            guava.Field(
                key="loss_type",
                description="The type of loss: fire, flood, theft, auto, or other",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="loss_description",
                description=(
                    "A brief description of what happened and the nature of the damage"
                ),
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="location_of_loss",
                description="The full address or location where the loss occurred",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="injuries_reported",
                description=(
                    "Whether any injuries were reported as part of this incident, "
                    "and if so, a brief description"
                ),
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="estimated_damage",
                description=(
                    "The policyholder's rough estimate of the total damage amount, "
                    "if they are able to provide one"
                ),
                field_type="text",
                required=False,
            ),
            guava.Field(
                key="best_callback_number",
                description="The best phone number to reach the policyholder for follow-up",
                field_type="text",
                required=True,
            ),
        ],
    )


@agent.on_task_complete("fnol")
def on_done(call: guava.Call) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "first_notice_of_loss",
        "policy_number": call.get_field("policy_number"),
        "policyholder_name": call.get_field("policyholder_name"),
        "loss_date": call.get_field("loss_date"),
        "loss_type": call.get_field("loss_type"),
        "loss_description": call.get_field("loss_description"),
        "location_of_loss": call.get_field("location_of_loss"),
        "injuries_reported": call.get_field("injuries_reported"),
        "estimated_damage": call.get_field("estimated_damage"),
        "best_callback_number": call.get_field("best_callback_number"),
    }
    print(json.dumps(results, indent=2))
    logging.info("FNOL results saved: %s", results)
    call.hangup(
        final_instructions=(
            "Thank you for providing all of that information. Your claim has been "
            "logged and a claim number will be sent to the email address on file "
            "within the next few minutes. A licensed adjuster from Keystone Property "
            "& Casualty will be in touch with you shortly to discuss next steps. "
            "We appreciate your patience and are here to help. Take care."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
