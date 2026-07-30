# SDK conformance: guava-sdk 0.35.0 (2026-07-21)
import argparse
import json
import logging
from datetime import datetime, time, timezone

import guava
from guava import logging_utils
from guava.helpers.llm import IntentRecognizer

BUSINESS_HOURS_START = time(8, 0)
BUSINESS_HOURS_END = time(20, 0)

L2_SUPPORT_LINE = "+15551000600"
BILLING_SALES_LINE = "+15551000601"


# ---------------------------------------------------------------------------
# Mock API — simulates account lookup and service status
# ---------------------------------------------------------------------------

MOCK_ACCOUNTS = {
    "NXM-880011": {
        "name": "David Park",
        "phone_on_account": "+15559990011",
        "plan": "Premium Unlimited",
        "device": "iPhone 15 Pro",
        "device_warranty": "active",
        "service_status": "active",
        "area_status": "normal",
        "recent_charges": [
            {"date": "2026-07-01", "description": "Monthly plan charge", "amount": "$85.00"},
            {"date": "2026-07-01", "description": "Device protection", "amount": "$15.00"},
            {"date": "2026-06-28", "description": "International roaming", "amount": "$12.50"},
        ],
    },
    "NXM-880022": {
        "name": "Maria Santos",
        "phone_on_account": "+15559990022",
        "plan": "Family Share 15GB",
        "device": "Samsung Galaxy S24",
        "device_warranty": "expired",
        "service_status": "active",
        "area_status": "outage",
        "recent_charges": [
            {"date": "2026-07-01", "description": "Monthly plan charge", "amount": "$70.00"},
            {"date": "2026-07-01", "description": "Overage charges (2.3GB)", "amount": "$23.00"},
        ],
    },
    "NXM-880033": {
        "name": "Rachel Kim",
        "phone_on_account": "+15559990033",
        "plan": "Essential 5GB",
        "device": "Google Pixel 8",
        "device_warranty": "active",
        "service_status": "suspended",
        "area_status": "normal",
        "recent_charges": [
            {"date": "2026-07-01", "description": "Monthly plan charge", "amount": "$45.00"},
            {"date": "2026-06-15", "description": "Late payment fee", "amount": "$10.00"},
        ],
    },
}


def lookup_account(account_number):
    return MOCK_ACCOUNTS.get(account_number)


# ---------------------------------------------------------------------------
# Inline knowledge base for common troubleshooting answers
# ---------------------------------------------------------------------------

KNOWLEDGE_BASE = {
    "restart_router": (
        "To restart your router: 1) Unplug the power cable from the back of the "
        "router. 2) Wait 30 seconds. 3) Plug the power cable back in. 4) Wait "
        "2 to 3 minutes for the lights to stabilize. 5) Try connecting again."
    ),
    "check_outage": (
        "You can check for outages in your area at nexusmobile.com/status or by "
        "texting STATUS to 611 from your Nexus Mobile phone."
    ),
    "reset_network": (
        "To reset network settings on most devices: Go to Settings > General > "
        "Transfer or Reset > Reset > Reset Network Settings. Note: this will "
        "remove saved Wi-Fi passwords."
    ),
    "sim_reseat": (
        "To reseat your SIM card: 1) Power off your device. 2) Use a SIM eject "
        "tool or paperclip to open the SIM tray. 3) Remove the SIM card, wait "
        "10 seconds, and reinsert it firmly. 4) Power the device back on."
    ),
    "warranty_check": (
        "Your device warranty covers manufacturing defects for one year from the "
        "purchase date. Accidental damage, water damage, and normal wear are not "
        "covered under the standard warranty. Device protection plans cover "
        "additional damage types."
    ),
    "billing_explanation": (
        "Your bill includes your monthly plan charge, any add-on services, device "
        "payments, taxes, and fees. Overage charges apply when you exceed your "
        "plan's data, minutes, or text limits. You can view a detailed breakdown "
        "in the Nexus Mobile app or at nexusmobile.com/billing."
    ),
    "payment_options": (
        "You can pay your bill online at nexusmobile.com, through the Nexus "
        "Mobile app, by calling 611 from your Nexus phone, or at any Nexus "
        "Mobile store location. We accept credit/debit cards, bank transfers, "
        "and cash (in-store only)."
    ),
}


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

agent = guava.Agent(
    name="Finley",
    organization="Nexus Mobile — Technical Support",
    purpose=(
        "assist customers calling in with technical issues by verifying their "
        "account, classifying their issue, guiding them through troubleshooting "
        "steps, and escalating to L2 support when needed"
    ),
)

_mid_call_intent = IntentRecognizer({
    "internet_issue": "The caller is having internet, data, or connectivity problems",
    "billing_issue": "The caller has a question about their bill, charges, or payments",
    "device_issue": "The caller is having a problem with their physical device or hardware",
    "account_issue": "The caller wants to make changes to their account, plan, or service",
    "other_issue": "The caller's issue does not fit the other categories",
})


def _is_business_hours():
    now = datetime.now().time()
    return BUSINESS_HOURS_START <= now < BUSINESS_HOURS_END


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    if _is_business_hours():
        return guava.AcceptCall()
    return guava.DeclineCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "verify_account",
        objective=(
            "Verify the caller's identity before providing any account-specific "
            "support. Collect their account number and the name on the account. "
            "Do not discuss account details, billing, or service status until "
            "identity is confirmed."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Nexus Mobile Technical Support. My name is "
                "Finley and I'm here to help you today. First, I'll need to verify "
                "your account."
            ),
            guava.Field(
                key="account_number",
                description="The caller's Nexus Mobile account number (format: NXM-NNNNNN)",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="account_name",
                description="The full name on the account for identity verification",
                field_type="text",
                required=True,
            ),
        ],
    )


@agent.on_validate("account_number")
def validate_account_number(call: guava.Call, value) -> bool | tuple[bool, str]:
    if isinstance(value, str) and value.upper().startswith("NXM-") and len(value) >= 8:
        return True
    return (
        False,
        "That doesn't look like a valid account number. It should start with "
        "NXM followed by a dash and six digits, like NXM-880011.",
    )


@agent.on_task_complete("verify_account")
def on_account_verified(call: guava.Call) -> None:
    account_number = call.get_field("account_number")
    account_name = call.get_field("account_name")
    account = lookup_account(account_number)

    if account is None or account["name"].lower() != account_name.lower():
        logging.warning("Account verification failed for %s.", account_number)
        call.hangup(
            final_instructions=(
                "Let the caller know that the information provided does not match "
                "our records. For security, you cannot proceed. Suggest they "
                "double-check their account number and try calling again, or visit "
                "a Nexus Mobile store with valid ID, and politely say goodbye."
            )
        )
        return

    call.set_variable("verified_name", account["name"])
    call.set_variable("account_number", account_number)
    call.set_variable("device", account["device"])
    call.set_variable("device_warranty", account["device_warranty"])
    call.set_variable("area_status", account["area_status"])
    call.set_variable("service_status", account["service_status"])

    call.add_info("account_info", {
        "account_number": account_number,
        "name": account["name"],
        "plan": account["plan"],
        "device": account["device"],
        "device_warranty": account["device_warranty"],
        "service_status": account["service_status"],
        "area_status": account["area_status"],
    })

    call.add_info("recent_charges", account["recent_charges"])

    call.add_info("troubleshooting_knowledge", {
        "router_restart": KNOWLEDGE_BASE["restart_router"],
        "check_outage": KNOWLEDGE_BASE["check_outage"],
        "reset_network": KNOWLEDGE_BASE["reset_network"],
        "sim_reseat": KNOWLEDGE_BASE["sim_reseat"],
        "warranty_info": KNOWLEDGE_BASE["warranty_check"],
        "billing_info": KNOWLEDGE_BASE["billing_explanation"],
        "payment_options": KNOWLEDGE_BASE["payment_options"],
    })

    call.set_task(
        "classify_issue",
        objective=(
            f"Account verified — the caller is {account['name']}. Now determine "
            f"what issue they are calling about. Ask them to describe their problem "
            f"in general terms so you can route them to the right troubleshooting path."
        ),
        checklist=[
            guava.Say(
                f"Thank you, {account['name']}. Your account has been verified. "
                f"How can I help you today? Please describe the issue you're "
                f"experiencing."
            ),
            guava.Field(
                key="issue_description",
                description="The caller's description of their issue in their own words",
                field_type="text",
                required=True,
            ),
        ],
    )


@agent.on_task_complete("classify_issue")
def on_issue_described(call: guava.Call) -> None:
    # The issue_description is collected; the on_action_request + IntentRecognizer
    # will classify the intent and route to the appropriate handler.
    # Set a fallback task to capture any issue that doesn't trigger an action.
    call.set_task(
        "general_troubleshoot",
        objective=(
            "The caller has described their issue. Based on their description, "
            "help them with basic troubleshooting. If their issue requires "
            "specialized help, let them know you'll connect them with the right team."
        ),
        checklist=[
            guava.Field(
                key="resolution_attempted",
                description="What troubleshooting steps were attempted",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="issue_resolved",
                description="Whether the issue was resolved during this call",
                field_type="multiple_choice",
                choices=["yes", "no", "partially"],
                required=True,
            ),
        ],
    )


@agent.on_action_request
def on_action_request(call: guava.Call, intent_summary: str):
    return _mid_call_intent.classify(intent_summary)


@agent.on_action("internet_issue")
def handle_internet(call: guava.Call) -> None:
    call.set_variable("issue_category", "internet")
    verified_name = call.get_variable("verified_name")
    area_status = call.get_variable("area_status")

    if area_status == "outage":
        call.set_task(
            "internet_troubleshoot",
            objective=(
                f"There is a known outage in {verified_name}'s area. Inform them "
                f"of the outage, explain that our engineering team is working on it, "
                f"and provide an estimated resolution time of 2 to 4 hours. "
                f"Do NOT have them troubleshoot — the issue is on our end."
            ),
            checklist=[
                guava.Say(
                    f"I can see there is currently a service outage affecting your "
                    f"area. Our engineering team is actively working on this and we "
                    f"expect it to be resolved within 2 to 4 hours. This is not an "
                    f"issue with your device or account."
                ),
                guava.Field(
                    key="resolution_attempted",
                    description="Steps taken or information provided",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="issue_resolved",
                    description="Whether the issue was resolved (outage cases are typically 'no' — awaiting fix)",
                    field_type="multiple_choice",
                    choices=["yes", "no", "partially"],
                    required=True,
                ),
            ],
        )
    else:
        call.set_task(
            "internet_troubleshoot",
            objective=(
                f"Guide {verified_name} through internet/connectivity troubleshooting. "
                f"No outage detected in their area. Steps: 1) Check if the issue "
                f"is Wi-Fi or cellular data. 2) If cellular, try toggling airplane "
                f"mode. 3) If that fails, guide through a network settings reset. "
                f"4) If still unresolved after two attempts, escalate to L2."
            ),
            checklist=[
                guava.Say(
                    f"I've checked our system and there are no outages affecting "
                    f"your area right now, so let's troubleshoot your connection."
                ),
                guava.Field(
                    key="connection_type",
                    description="Whether the issue is with Wi-Fi, cellular data, or both",
                    field_type="multiple_choice",
                    choices=["wifi", "cellular", "both"],
                    required=True,
                ),
                guava.Field(
                    key="resolution_attempted",
                    description="What troubleshooting steps were attempted and their results",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="issue_resolved",
                    description="Whether the connectivity issue was resolved",
                    field_type="multiple_choice",
                    choices=["yes", "no", "partially"],
                    required=True,
                ),
            ],
        )


@agent.on_action("billing_issue")
def handle_billing(call: guava.Call) -> None:
    call.set_variable("issue_category", "billing")
    verified_name = call.get_variable("verified_name")
    call.set_task(
        "billing_review",
        objective=(
            f"Help {verified_name} understand their recent charges. Present the "
            f"charge details that have been loaded into the call. Explain each "
            f"line item clearly. "
            f"GUARDRAIL: Do NOT make any account changes, plan modifications, or "
            f"process refunds. If the customer wants changes or disputes a charge, "
            f"transfer them to the billing department."
        ),
        checklist=[
            guava.Say(
                f"I can help you understand your recent charges. Let me pull those "
                f"up for you."
            ),
            guava.Field(
                key="billing_concern",
                description="What specific charge or billing question the customer has",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="resolution_attempted",
                description="What was explained or resolved regarding the billing question",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="issue_resolved",
                description="Whether the billing question was resolved",
                field_type="multiple_choice",
                choices=["yes", "no", "needs_billing_team"],
                required=True,
            ),
        ],
    )


@agent.on_action("device_issue")
def handle_device(call: guava.Call) -> None:
    call.set_variable("issue_category", "device")
    verified_name = call.get_variable("verified_name")
    device = call.get_variable("device")
    warranty = call.get_variable("device_warranty")
    warranty_note = (
        "Their device warranty is active."
        if warranty == "active"
        else "Their device warranty has expired."
    )

    call.set_task(
        "device_troubleshoot",
        objective=(
            f"Help {verified_name} with their {device} issue. {warranty_note} "
            f"Guide through basic troubleshooting: 1) Describe the issue. "
            f"2) Try a soft restart (hold power button, slide to power off, "
            f"wait 10 seconds, power on). 3) If that doesn't help, try a SIM "
            f"reseat. If the issue persists after two attempts, escalate to L2 "
            f"and mention warranty status."
        ),
        checklist=[
            guava.Field(
                key="device_symptom",
                description="The specific symptom or malfunction the customer is experiencing",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="resolution_attempted",
                description="What troubleshooting steps were attempted and their results",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="issue_resolved",
                description="Whether the device issue was resolved",
                field_type="multiple_choice",
                choices=["yes", "no", "needs_repair"],
                required=True,
            ),
        ],
    )


@agent.on_action("account_issue")
def handle_account(call: guava.Call) -> None:
    call.set_variable("issue_category", "account")
    call.transfer(
        destination=BILLING_SALES_LINE,
        instructions=(
            "The customer wants to make account changes (plan changes, "
            "cancellations, or account modifications). These cannot be handled "
            "by technical support. Connect them with the billing and sales team. "
            "Let the customer know you're transferring them to the right department."
        ),
    )


@agent.on_action("other_issue")
def handle_other(call: guava.Call) -> None:
    call.set_variable("issue_category", "other")
    verified_name = call.get_variable("verified_name")
    call.set_task(
        "general_troubleshoot",
        objective=(
            f"Help {verified_name} with their issue. Gather details and attempt "
            f"basic troubleshooting. If the issue is beyond L1 support scope, "
            f"escalate to L2."
        ),
        checklist=[
            guava.Field(
                key="resolution_attempted",
                description="What troubleshooting steps were attempted",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="issue_resolved",
                description="Whether the issue was resolved",
                field_type="multiple_choice",
                choices=["yes", "no", "partially"],
                required=True,
            ),
        ],
    )


def _finalize_support(call: guava.Call) -> None:
    issue_resolved = call.get_field("issue_resolved")
    verified_name = call.get_variable("verified_name")

    if issue_resolved in ("no", "needs_repair", "needs_billing_team"):
        if issue_resolved == "needs_billing_team":
            call.transfer(
                destination=BILLING_SALES_LINE,
                instructions=(
                    f"Connect {verified_name} with the billing team. Their account "
                    f"details and billing concern have been captured."
                ),
            )
        else:
            call.transfer(
                destination=L2_SUPPORT_LINE,
                instructions=(
                    f"Connect {verified_name} with L2 technical support. Their "
                    f"account details, issue description, and troubleshooting steps "
                    f"attempted have been captured in the call."
                ),
            )
    else:
        call.hangup(
            final_instructions=(
                f"Let {verified_name} know they can call back anytime or visit "
                f"nexusmobile.com for additional help, and politely say goodbye."
            )
        )


@agent.on_task_complete("internet_troubleshoot")
def on_internet_done(call: guava.Call) -> None:
    _finalize_support(call)


@agent.on_task_complete("billing_review")
def on_billing_done(call: guava.Call) -> None:
    _finalize_support(call)


@agent.on_task_complete("device_troubleshoot")
def on_device_done(call: guava.Call) -> None:
    _finalize_support(call)


@agent.on_task_complete("general_troubleshoot")
def on_general_done(call: guava.Call) -> None:
    _finalize_support(call)


@agent.on_question
def on_question(call: guava.Call, question: str) -> str:
    question_lower = question.lower()

    if any(kw in question_lower for kw in ("restart", "reboot", "router", "modem")):
        return KNOWLEDGE_BASE["restart_router"]
    if any(kw in question_lower for kw in ("outage", "down", "status")):
        return KNOWLEDGE_BASE["check_outage"]
    if any(kw in question_lower for kw in ("network settings", "reset network", "apn")):
        return KNOWLEDGE_BASE["reset_network"]
    if any(kw in question_lower for kw in ("sim", "sim card", "reseat")):
        return KNOWLEDGE_BASE["sim_reseat"]
    if any(kw in question_lower for kw in ("warranty", "covered", "protection")):
        return KNOWLEDGE_BASE["warranty_check"]
    if any(kw in question_lower for kw in ("bill", "charge", "invoice", "statement")):
        return KNOWLEDGE_BASE["billing_explanation"]
    if any(kw in question_lower for kw in ("pay", "payment", "how to pay")):
        return KNOWLEDGE_BASE["payment_options"]

    return (
        "I don't have specific information on that topic. Let me note your "
        "question and if I'm not able to help, I'll connect you with a "
        "specialist who can."
    )


@agent.on_session_end
def on_session_end(call: guava.Call, event: guava.BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "tech_support_triage",
        "verified_name": call.get_variable("verified_name"),
        "account_number": call.get_variable("account_number"),
        "device": call.get_variable("device"),
        "area_status": call.get_variable("area_status"),
        "service_status": call.get_variable("service_status"),
        "issue_description": call.get_field("issue_description"),
        "issue_category": call.get_variable("issue_category"),
        "connection_type": call.get_field("connection_type"),
        "device_symptom": call.get_field("device_symptom"),
        "billing_concern": call.get_field("billing_concern"),
        "resolution_attempted": call.get_field("resolution_attempted"),
        "issue_resolved": call.get_field("issue_resolved"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()

    parser = argparse.ArgumentParser(
        description="Inbound technical support triage agent for Nexus Mobile"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--phone", metavar="PHONE_NUMBER", nargs="?", const="", help="Listen for phone calls."
    )
    group.add_argument(
        "--webrtc", metavar="WEBRTC_CODE", nargs="?", const="", help="Listen on a WebRTC code."
    )
    group.add_argument("--local", action="store_true", help="Start a local call.")
    group.add_argument("--sip", metavar="SIP_CODE", help="Listen on a SIP code 'guavasip-...'.")
    group.add_argument(
        "--call", metavar="PHONE_NUMBER", help="Place an outbound call for testing."
    )
    parser.add_argument(
        "--from-number", metavar="FROM_NUMBER", help="Caller ID for --call mode."
    )
    args = parser.parse_args()

    if args.call:
        agent.call_phone(args.from_number or "", args.call)
    elif args.phone is not None:
        agent.listen_phone(args.phone)
    elif args.webrtc is not None:
        agent.listen_webrtc(args.webrtc or None)
    elif args.sip:
        agent.listen_sip(args.sip)
    else:
        agent.call_local()
