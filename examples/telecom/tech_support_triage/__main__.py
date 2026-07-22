# SDK conformance: guava-sdk 0.35.0 (2026-07-21)
import json
import logging
import argparse
from datetime import datetime, timezone

import guava
from guava import logging_utils

agent = guava.Agent(
    name="Casey",
    organization="Nexus Mobile - Technical Support",
    purpose=(
        "to greet customers calling in with technical issues, collect structured "
        "troubleshooting information to create an accurate support ticket, and "
        "ensure they are connected with the right technician as quickly as possible"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "support_triage",
        objective=(
            "A customer has called Nexus Mobile Technical Support. Greet them warmly, "
            "collect all the information needed to open a complete support ticket, "
            "and let them know a technician will be in touch. Be patient, clear, "
            "and professional throughout the call."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Nexus Mobile Technical Support. My name is Casey "
                "and I'm here to help you today. I'll be collecting some information so "
                "we can get the right technician working on your issue as quickly as possible."
            ),
            guava.Field(
                key="caller_name",
                description="Ask the caller for their full name.",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="account_number",
                description=(
                    "Ask the caller for their Nexus Mobile account number. "
                    "If they do not have it handy, ask for the phone number on the account."
                ),
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="device_model",
                description=(
                    "Ask the caller what device they are experiencing issues with — "
                    "including the make and model if possible (e.g. iPhone 15 Pro, "
                    "Samsung Galaxy S24, etc.)."
                ),
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="issue_category",
                description=(
                    "Ask the caller to describe what type of issue they are experiencing "
                    "and categorize their answer."
                ),
                field_type="multiple_choice",
                choices=["no_signal", "slow_data", "call_quality", "billing", "device_hardware", "other"],
                required=True,
            ),
            guava.Field(
                key="issue_description",
                description=(
                    "Ask the caller to describe the issue in their own words. "
                    "Capture a clear and detailed description of what is happening."
                ),
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="issue_started",
                description=(
                    "Ask the caller when they first noticed the issue — today, yesterday, "
                    "or how many days ago. Capture the timeframe they describe."
                ),
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="already_rebooted",
                description=(
                    "Ask the caller if they have already tried rebooting or restarting "
                    "their device since the issue began."
                ),
                field_type="multiple_choice",
                choices=["yes", "no"],
                required=True,
            ),
            guava.Field(
                key="technician_callback_number",
                description=(
                    "Ask the caller for the best phone number for a technician to reach "
                    "them on for a callback. Confirm the number back to them."
                ),
                field_type="text",
                required=True,
            ),
        ],
    )


@agent.on_task_complete("support_triage")
def on_done(call: guava.Call) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "Casey",
        "organization": "Nexus Mobile - Technical Support",
        "use_case": "tech_support_triage",
        "fields": {
            "caller_name": call.get_field("caller_name"),
            "account_number": call.get_field("account_number"),
            "device_model": call.get_field("device_model"),
            "issue_category": call.get_field("issue_category"),
            "issue_description": call.get_field("issue_description"),
            "issue_started": call.get_field("issue_started"),
            "already_rebooted": call.get_field("already_rebooted"),
            "technician_callback_number": call.get_field("technician_callback_number"),
        },
    }
    print(json.dumps(results, indent=2))
    logging.info("Tech support triage ticket saved.")
    call.hangup(
        final_instructions=(
            "Let the customer know that their support ticket has been created and provide "
            "them with a ticket number (you may use a placeholder such as 'TKT-XXXXXX'). "
            "Inform them that a Nexus Mobile technician will call them back within 2 to 4 "
            "business hours at the number they provided. Thank them for calling and wish "
            "them a good day."
        )
    )


@agent.on_session_end
def on_session_end(call: guava.Call) -> None:
    logging.info("Session ended — collected fields: %s", json.dumps({
        "caller_name": call.get_field("caller_name"),
        "account_number": call.get_field("account_number"),
        "device_model": call.get_field("device_model"),
        "issue_category": call.get_field("issue_category"),
        "issue_description": call.get_field("issue_description"),
        "issue_started": call.get_field("issue_started"),
        "already_rebooted": call.get_field("already_rebooted"),
        "technician_callback_number": call.get_field("technician_callback_number"),
    }, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()

    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--phone", metavar="PHONE_NUMBER", nargs="?", const="", help="Listen for phone calls."
    )
    group.add_argument(
        "--webrtc", metavar="WEBRTC_CODE", nargs="?", const="", help="Listen on a WebRTC code."
    )
    group.add_argument("--local", action="store_true", help="Start a local call.")
    group.add_argument("--sip", metavar="SIP_CODE", help="Listen on a SIP code 'guavasip-...'.")
    args = parser.parse_args()

    if args.phone is not None:
        agent.listen_phone(args.phone)
    elif args.webrtc is not None:
        agent.listen_webrtc(args.webrtc or None)
    elif args.sip:
        agent.listen_sip(args.sip)
    else:
        agent.call_local()
