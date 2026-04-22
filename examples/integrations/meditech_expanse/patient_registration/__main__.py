import guava
import os
import logging
from guava import logging_utils
import requests
from datetime import datetime


FHIR_BASE_URL = os.environ["MEDITECH_FHIR_BASE_URL"]


def get_headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ['MEDITECH_ACCESS_TOKEN']}",
        "Content-Type": "application/json",
        "Accept": "application/fhir+json",
    }


class PatientRegistrationController(guava.CallController):
    def __init__(self):
        super().__init__()
        self.existing_patient_id = None

        self.set_persona(
            organization_name="St. Raphael Medical Center",
            agent_name="Morgan",
            agent_purpose=(
                "to help patients provide or update their demographic and insurance "
                "information before a visit to St. Raphael Medical Center"
            ),
        )

        self.set_task(
            objective=(
                "A patient has called St. Raphael Medical Center to pre-register or update "
                "their information before an upcoming visit. Greet them warmly, collect their "
                "demographics and insurance details, and save their record in Meditech."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling St. Raphael Medical Center. My name is Morgan. "
                    "I can help you pre-register or update your information before your visit. "
                    "This will just take a few minutes."
                ),
                guava.Field(
                    key="first_name",
                    description="Ask the caller for their first name.",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="last_name",
                    description="Ask the caller for their last name.",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="date_of_birth",
                    description=(
                        "Ask for the patient's date of birth to locate or create their record. "
                        "Capture in YYYY-MM-DD format (e.g. 1978-11-04)."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="address_line",
                    description=(
                        "Ask for the patient's street address including house number and street name."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="city",
                    description="Ask for the city the patient lives in.",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="state",
                    description=(
                        "Ask for the two-letter state abbreviation for the patient's address "
                        "(e.g. CA, NY, TX)."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="zip_code",
                    description="Ask for the patient's ZIP code.",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="phone",
                    description=(
                        "Ask for the best phone number to reach the patient. "
                        "Capture the digits only, no formatting required."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="email",
                    description=(
                        "Ask for the patient's email address for appointment confirmations "
                        "and patient portal access."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="insurance_provider",
                    description=(
                        "Ask which insurance provider the patient is covered under. "
                        "Options are: Medicare, Medicaid, Blue Cross Blue Shield, Aetna, "
                        "United Healthcare, Cigna, or Other."
                    ),
                    field_type="multiple_choice",
                    choices=[
                        "Medicare",
                        "Medicaid",
                        "Blue Cross Blue Shield",
                        "Aetna",
                        "United Healthcare",
                        "Cigna",
                        "Other",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="insurance_member_id",
                    description=(
                        "Ask for the patient's insurance member ID as it appears on their "
                        "insurance card."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="insurance_group_number",
                    description=(
                        "Ask for the group number on the patient's insurance card. "
                        "If they don't have one or it's not applicable, capture 'none'."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="emergency_contact_name",
                    description=(
                        "Ask for the full name of the patient's emergency contact."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="emergency_contact_phone",
                    description=(
                        "Ask for the phone number of the patient's emergency contact. "
                        "Capture digits only."
                    ),
                    field_type="text",
                    required=True,
                ),
            ],
            on_complete=self.save_registration,
        )

        self.accept_call()

    def save_registration(self):
        first_name = self.get_field("first_name")
        last_name = self.get_field("last_name")
        dob = self.get_field("date_of_birth")
        address_line = self.get_field("address_line")
        city = self.get_field("city")
        state = self.get_field("state")
        zip_code = self.get_field("zip_code")
        phone = self.get_field("phone")
        email = self.get_field("email")
        insurance_provider = self.get_field("insurance_provider")
        insurance_member_id = self.get_field("insurance_member_id")
        insurance_group_number = self.get_field("insurance_group_number")
        emergency_contact_name = self.get_field("emergency_contact_name")
        emergency_contact_phone = self.get_field("emergency_contact_phone")

        logging.info("Registration fields collected for %s %s.", first_name, last_name)

        # Search Meditech for an existing patient by last name and date of birth
        # before deciding whether to PUT (full update) or POST (create new).
        try:
            search_resp = requests.get(
                f"{FHIR_BASE_URL}/Patient",
                headers=get_headers(),
                params={"family": last_name, "birthdate": dob},
                timeout=10,
            )
            search_resp.raise_for_status()
            entries = search_resp.json().get("entry", [])
            if entries:
                self.existing_patient_id = entries[0]["resource"]["id"]
                logging.info(
                    "Existing Meditech patient found: %s", self.existing_patient_id
                )
        except Exception as e:
            logging.error("Failed to search Meditech Patient: %s", e)

        # Build the full FHIR Patient resource with all collected demographics,
        # address, telecom, insurance identifier, and emergency contact.
        patient_resource: dict = {
            "resourceType": "Patient",
            "name": [
                {
                    "use": "official",
                    "family": last_name,
                    "given": [first_name],
                }
            ],
            "birthDate": dob,
            "telecom": [
                {"system": "phone", "value": phone, "use": "mobile"},
                {"system": "email", "value": email},
            ],
            "address": [
                {
                    "use": "home",
                    "line": [address_line],
                    "city": city,
                    "state": state,
                    "postalCode": zip_code,
                    "country": "US",
                }
            ],
            "identifier": [
                {
                    "system": "urn:oid:2.16.840.1.113883.4.6",
                    "value": insurance_member_id,
                    "assigner": {"display": insurance_provider},
                    "extension": [
                        {
                            "url": (
                                "http://straphael.org/fhir/StructureDefinition/insurance-group-number"
                            ),
                            "valueString": insurance_group_number,
                        }
                    ],
                }
            ],
            "contact": [
                {
                    "relationship": [
                        {
                            "coding": [
                                {
                                    "system": "http://terminology.hl7.org/CodeSystem/v2-0131",
                                    "code": "C",
                                    "display": "Emergency Contact",
                                }
                            ]
                        }
                    ],
                    "name": {"text": emergency_contact_name},
                    "telecom": [
                        {"system": "phone", "value": emergency_contact_phone}
                    ],
                }
            ],
        }

        if self.existing_patient_id:
            # Patient exists — issue a PUT to fully replace the demographic record in Meditech.
            # PUT is preferred over PATCH here because we collected all fields and want to
            # ensure the stored record reflects the patient's current information completely.
            patient_resource["id"] = self.existing_patient_id
            try:
                resp = requests.put(
                    f"{FHIR_BASE_URL}/Patient/{self.existing_patient_id}",
                    headers=get_headers(),
                    json=patient_resource,
                    timeout=10,
                )
                resp.raise_for_status()
                logging.info(
                    "PUT updated Meditech Patient %s for %s %s.",
                    self.existing_patient_id,
                    first_name,
                    last_name,
                )
            except Exception as e:
                logging.error(
                    "Failed to PUT update Meditech Patient %s: %s",
                    self.existing_patient_id,
                    e,
                )

            self.hangup(
                final_instructions=(
                    f"Let {first_name} know that their existing record at St. Raphael Medical "
                    "Center has been fully updated with the information they provided today — "
                    "including their address, contact details, and insurance. Let them know a "
                    "patient services coordinator will be in touch before their visit if anything "
                    "else is needed. Thank them for calling and wish them a great day."
                )
            )

        else:
            # New patient — POST a fresh Patient resource to Meditech Expanse.
            try:
                resp = requests.post(
                    f"{FHIR_BASE_URL}/Patient",
                    headers=get_headers(),
                    json=patient_resource,
                    timeout=10,
                )
                resp.raise_for_status()
                new_id = resp.json().get("id", "")
                logging.info(
                    "Created new Meditech Patient %s for %s %s.", new_id, first_name, last_name
                )
            except Exception as e:
                logging.error(
                    "Failed to POST new Meditech Patient for %s %s: %s",
                    first_name,
                    last_name,
                    e,
                )

            self.hangup(
                final_instructions=(
                    f"Thank {first_name} for pre-registering with St. Raphael Medical Center. "
                    "Let them know their record has been created and our care team will be ready "
                    "for them on their visit date. Mention they may receive a welcome email with "
                    "patient portal setup instructions. Remind them to bring their insurance card "
                    "and a valid photo ID. Wish them a great day."
                )
            )


if __name__ == "__main__":
    logging_utils.configure_logging()
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=PatientRegistrationController,
    )
