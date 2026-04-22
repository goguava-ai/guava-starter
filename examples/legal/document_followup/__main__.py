import guava
import os
import logging
import json
import argparse
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)


class DocumentFollowupController(guava.CallController):
    def __init__(self, contact_name, matter_number, requested_documents):
        super().__init__()
        self.contact_name = contact_name
        self.matter_number = matter_number
        self.requested_documents = requested_documents
        self.set_persona(
            organization_name="Hargrove & Associates Law Firm",
            agent_name="Casey",
            agent_purpose=(
                "to follow up on outstanding document requests related to a legal "
                "matter and log the client's response regarding availability and "
                "submission details"
            ),
        )
        self.reach_person(
            contact_full_name=self.contact_name,
            on_success=self.begin_document_followup,
            on_failure=self.recipient_unavailable,
        )

    def begin_document_followup(self):
        self.set_task(
            objective=(
                f"Follow up on outstanding documents for matter number "
                f"{self.matter_number}. The documents previously requested are: "
                f"{self.requested_documents}. Determine whether the documents are "
                "ready, how and when they will be submitted, and note anything the "
                "client is unable to provide. Remain professional and understanding."
            ),
            checklist=[
                guava.Say(
                    f"Good day. I am calling from Hargrove and Associates Law Firm "
                    f"regarding matter number {self.matter_number}. We had previously "
                    f"sent a request for certain documents, specifically: "
                    f"{self.requested_documents}. I am following up to check on the "
                    "status of those documents and to help coordinate their submission."
                ),
                guava.Field(
                    key="documents_ready",
                    description=(
                        "Whether the requested documents are ready or nearly ready "
                        "to be submitted"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="submission_method",
                    description=(
                        "How the client intends to submit the documents: by email, "
                        "by mail, by dropping them off at the office, or by fax"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="submission_date",
                    description=(
                        "The date by which the client expects to submit the documents"
                    ),
                    field_type="date",
                    required=True,
                ),
                guava.Field(
                    key="documents_cannot_provide",
                    description=(
                        "A description of any documents from the request that the "
                        "client is unable to provide, along with the reason why "
                        "— for example, documents that no longer exist, were never "
                        "in their possession, or require a third-party release"
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="additional_documents_offered",
                    description=(
                        "Any additional documents the client is willing to provide "
                        "beyond those specifically requested, which may be relevant "
                        "to the matter"
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
            on_complete=self.save_results,
        )

    def save_results(self):
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "call_type": "outbound_document_followup",
            "meta": {
                "contact_name": self.contact_name,
                "matter_number": self.matter_number,
                "requested_documents": self.requested_documents,
            },
            "fields": {
                "documents_ready": self.get_field("documents_ready"),
                "submission_method": self.get_field("submission_method"),
                "submission_date": self.get_field("submission_date"),
                "documents_cannot_provide": self.get_field("documents_cannot_provide"),
                "additional_documents_offered": self.get_field(
                    "additional_documents_offered"
                ),
            },
        }
        print(json.dumps(results, indent=2))
        logging.info("Document follow-up results saved.")
        self.hangup(
            final_instructions=(
                "Thank the client by name for their time and assistance. Confirm the "
                "submission date and method they provided. Let them know that if they "
                "have any questions about what is needed or need assistance with "
                "submission, they should not hesitate to contact the firm directly. "
                "Say goodbye professionally."
            )
        )

    def recipient_unavailable(self):
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "call_type": "outbound_document_followup",
            "status": "recipient_unavailable",
            "meta": {
                "contact_name": self.contact_name,
                "matter_number": self.matter_number,
                "requested_documents": self.requested_documents,
            },
        }
        print(json.dumps(results, indent=2))
        logging.info("Recipient unavailable for document follow-up call.")
        self.hangup(
            final_instructions=(
                "Leave a brief, professional voicemail identifying yourself as Casey "
                "calling from Hargrove and Associates Law Firm. State that you are "
                f"following up on an outstanding document request for matter number "
                f"{self.matter_number} and ask that they return your call at their "
                "earliest convenience. Provide the firm's main number and say goodbye."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Outbound document follow-up call — Hargrove & Associates"
    )
    parser.add_argument("phone", help="Recipient phone number to dial")
    parser.add_argument("--name", required=True, help="Full name of the contact")
    parser.add_argument("--matter-number", required=True, help="Matter or case number")
    parser.add_argument(
        "--requested-documents",
        required=True,
        help="Description of the outstanding documents being followed up on",
    )
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=DocumentFollowupController(
            contact_name=args.name,
            matter_number=args.matter_number,
            requested_documents=args.requested_documents,
        ),
    )
