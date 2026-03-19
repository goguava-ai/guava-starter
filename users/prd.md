# Voice Agent PRD — Guava Kickoff Template

> **What this is:** A product requirements document (PRD) for your Guava voice agent demo.
> Fill this out before writing any code. Once complete, hand it to your AI coding assistant
> (Claude or similar) and ask it to build a Python demo based on this spec.
>
> **Two ways to fill this out:**
>
> - **Self-serve:** Read each section and fill in your answers directly in this file.
>   Required fields are marked **[REQUIRED]**. Everything else is optional but recommended.
>
> - **AI-assisted:** Open this file alongside your AI coding assistant and say:
>   *"Walk me through this PRD template and ask me one section at a time."*
>   The assistant will ask you questions, help you think through edge cases, and fill in
>   the document for you before generating any code.
>
> **When you're done:** Say to your assistant:
> *"Build a Python demo in this directory based on my PRD."*

---

## 1. Project Overview [REQUIRED]

**Project / use case name:**
<!-- A short name for this voice agent. E.g. "Appointment Reminder Bot", "Inbound Support Triage" -->


**Company or organization:**
<!-- Who is running this agent? E.g. "Acme Dental Group", "City of Springfield" -->


**Industry / vertical:**
<!-- E.g. Healthcare, Financial Services, Real Estate, Retail, Legal, Government, Education, etc. -->


**One-sentence description:**
<!-- What does this agent do? E.g. "Calls patients to remind them of upcoming appointments and reschedule cancellations." -->


**Longer description (optional):**
<!-- Add any helpful context: why this problem needs solving, what currently happens without the agent, etc. -->


---

## 2. Call Configuration [REQUIRED]

**Direction:**
<!-- Mark one: -->
- [ ] Outbound — the agent calls people
- [ ] Inbound — people call the agent
- [ ] Both

**Channel:**
<!-- Mark all that apply: -->
- [ ] Phone (PSTN)
- [ ] Web / browser (WebRTC)
- [ ] Local / edge device

**If outbound — who is being called?**
<!-- E.g. "Existing patients with appointments in the next 48 hours", "Customers with overdue invoices" -->


**If inbound — what triggers someone to call?**
<!-- E.g. "Customer sees a support number on their invoice", "Resident calls about a permit application" -->


---

## 3. Agent Persona [REQUIRED]

**Organization name (as the agent will introduce itself):**
<!-- E.g. "Bright Smile Dental", "Metro Power & Light", "Hargrove & Associates" -->


**Agent name:**
<!-- First name the agent will use. E.g. "Jordan", "Sam", "Alex" -->


**Agent personality / tone:**
<!-- E.g. "Warm and reassuring", "Professional and efficient", "Friendly but concise" -->


**Agent purpose (1–2 sentences the agent would say about its role):**
<!-- E.g. "I'm calling on behalf of Bright Smile Dental to help you schedule your upcoming appointment." -->


---

## 4. Core Task [REQUIRED]

**Primary objective:**
<!-- What must the agent accomplish on this call? Be specific.
     E.g. "Collect the patient's preferred reschedule date and confirm it back to them." -->


**Information the agent needs to collect:**
<!-- List each piece of data, its type, and whether it's required.
     Types: text, integer, date
     Format: - field_name (type) [required/optional] — description
     Example:
     - appointment_confirmed (text) [required] — Does the patient want to keep or reschedule?
     - reschedule_date (date) [optional] — Preferred new date if rescheduling -->


**Is there a known person the agent is trying to reach? (for outbound)**
<!-- Yes / No. If yes, the agent will confirm it has the right person before proceeding. -->


**What should happen when the call is complete?**
<!-- E.g. "Print collected fields to console", "Webhook to CRM", "Write to a CSV", "Nothing — demo only" -->


---

## 5. Call Flow

> Optional — fill out what you know. Leave blank and let your assistant fill in the gaps.

**Opening script (what the agent says first):**
<!-- Write it out or describe the gist.
     E.g. "Hello, this is Jordan calling from Bright Smile Dental. Am I speaking with [Name]?" -->


**Key steps / sequence:**
<!-- Describe the flow in plain language. E.g.:
     1. Confirm identity
     2. Remind about appointment on [date]
     3. Ask if they'll keep or reschedule
     4. If rescheduling, collect preferred dates
     5. Confirm new appointment and say goodbye -->


**Common variations / branches:**
<!-- What are the most likely things that can happen differently?
     E.g. "Patient wants to reschedule", "Patient says they already cancelled", "Wrong number" -->


**Closing line:**
<!-- What does the agent say to wrap up? E.g. "Thank you for your time — have a great day!" -->


---

## 6. Escalation & Fallback

> Optional but strongly recommended for production use cases.

**Should the agent ever transfer to a human?**
<!-- Yes / No. If yes, describe when. E.g. "If the caller is upset or asks to speak to someone." -->


**What is the transfer / escalation path?**
<!-- E.g. "Transfer to the front desk at ext. 100", "Tell them to call back during business hours", "Offer a callback" -->


**What should the agent do if it can't reach anyone?**
<!-- E.g. "Leave a voicemail", "Log the attempt and hang up", "Try again later" -->


**What should the agent do if it encounters an unexpected question?**
<!-- E.g. "Say it can't answer that and offer to connect them with a human",
     "Answer from a knowledge base document (attach below under Integrations)" -->


---

## 7. Integrations

> Optional — describe any external systems the agent should connect to.

**CRM or database lookup:**
<!-- Does the agent need to look up caller information before the call?
     E.g. "Look up patient record by phone number to get their name and appointment date" -->


**Data submission:**
<!-- Should collected fields be written somewhere after the call?
     E.g. "POST to https://... with the field JSON", "Write a row to appointments.csv", "Demo only — just print" -->


**Knowledge base / document:**
<!-- Should the agent be able to answer caller questions from a document?
     E.g. "FAQ document about our return policy" — paste the document text or a path below -->


**Other APIs or tools:**
<!-- Any other external calls the agent needs to make during the conversation? -->


---

## 8. Volume & Performance

> Optional — helps size the solution and set expectations.

**Expected call volume:**
<!-- E.g. "~200 calls/day", "Burst of 500 on Monday mornings", "Low — just a demo" -->


**Target average call duration:**
<!-- E.g. "Under 3 minutes", "2–5 minutes", "Unknown" -->


**Time-of-day or scheduling constraints:**
<!-- E.g. "Outbound calls only between 9am–8pm local time", "Inbound 24/7" -->


**Retry behavior (outbound):**
<!-- E.g. "Try twice if no answer, 30 minutes apart", "Call once only", "Not applicable" -->


---

## 9. Compliance & Legal

> Optional — important for regulated industries.

**Do calls need to be recorded?**
<!-- Yes / No / Unknown -->


**Any consent or disclosure requirements?**
<!-- E.g. "Must state call may be recorded", "TCPA opt-in required", "HIPAA — no PHI on voicemail" -->


**Geographic restrictions:**
<!-- E.g. "US only", "California — must follow CCPA", "No restrictions" -->


**Multi-language requirements:**
<!-- E.g. "English only", "English and Spanish", "Detect and match caller language" -->


---

## 10. Success Criteria

> Optional — helps your assistant write cleaner code and tests.

**What does a fully successful call look like?**
<!-- Describe the ideal outcome. E.g. "Agent reaches the patient, confirms the appointment, and logs the result." -->


**What does a partial success look like?**
<!-- E.g. "Agent reaches voicemail and leaves a message", "Caller declines to answer but is polite" -->


**What does a failure look like?**
<!-- E.g. "Wrong number", "Caller hangs up before completing the checklist", "No answer after retries" -->


**How will you measure if this is working?**
<!-- E.g. "% of calls where all required fields are collected", "Human spot-check of 10% of calls", "Demo only — eyeball test" -->


---

## 11. Sample Data

> Optional but highly recommended — makes the generated demo immediately runnable.

**Example caller / recipient:**
<!-- Provide a realistic test record. E.g.:
     Name: Jane Smith
     Phone: +15551234567
     Appointment: Thursday, March 5 at 10:30 AM -->


**Example inputs for any CLI args:**
<!-- If outbound, what would a realistic `python -m ... <args>` command look like?
     E.g. `python -m users.acme_dental +15551234567 --name "Jane Smith" --appointment "March 5 at 10:30 AM"` -->


---

## 12. Additional Notes

> Anything else your AI coding assistant should know before building the demo.


---

## Next Steps

Once this PRD is filled out (fully or partially), say the following to your AI coding assistant:

> *"Read my PRD at `users/<your_folder>/prd.md` and build a Python Guava voice agent demo
> in the same directory. Ask me any clarifying questions before writing code."*

Your assistant will:
1. Read this document
2. Ask follow-up questions about anything ambiguous or missing
3. Build a `__main__.py` in your folder, runnable as `python3 -m users.<your_folder>`
4. Optionally create supporting files (mock data, helpers) as needed

**Reference examples** — browse `/examples/<vertical>/` for working demos similar to your use case.
The `/docs/sdk-reference.md` and `/docs/quickstart.md` files document the full Guava SDK.
