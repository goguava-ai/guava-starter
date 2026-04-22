# SDK Reference

## Agent

`guava.Agent` is the entry point for building Guava voice agents. It holds the agent's identity and serves as the attachment point for all event handlers.

```python
import guava

agent = guava.Agent(
    name="Nova",          # Optional. The name the agent uses with callers.
    organization="Acme Corp",  # Optional. The organization the agent represents.
    purpose="Help customers with their orders.",  # Optional. High-level role description for the LLM.
)
```

Attach event handlers using decorators, then start the agent on a channel:

```python
@agent.on_call_start
def on_call_start(call: guava.Call):
    ...

agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
```

---

## Tasks

`call.set_task()` defines the agent's current objective during a call. It can be called at any point — including from callbacks or separate threads — to change the agent's goal dynamically.

```python
call.set_task(
    task_id,           # str. Unique identifier used to bind on_task_complete handlers.
    objective="",      # str. High-level goal providing context to the agent.
    checklist=[],      # list[Field | Say | str]. Ordered items the agent must complete.
    completion_criteria="",  # str. Additional guidance for open-ended tasks.
)
# Note: At least one of objective or checklist should be provided.
```

The `checklist` accepts three element types:

| Type | Purpose |
|------|---------|
| `guava.Field` | Collect structured information from the caller |
| `guava.Say` | Speak verbatim text |
| `str` | Provide flexible natural-language instructions to the agent |

**Example:**

```python
@agent.on_call_start
def on_call_start(call: guava.Call):
    call.set_task(
        "waitlist",
        objective="You are a virtual assistant for Thai Palace. Add callers to the waitlist.",
        checklist=[
            guava.Field(key="caller_name", field_type="text", description="Name for the waitlist"),
            guava.Field(key="party_size", field_type="integer", description="Number of people"),
            guava.Field(
                key="phone_number",
                field_type="text",
                description="Phone number to text when the table is ready",
            ),
            "Read the phone number back to the caller to confirm.",
        ],
    )

@agent.on_task_complete("waitlist")
def on_waitlist_done(call: guava.Call):
    logger.info("Added %s, party of %d, to waitlist.",
        call.get_field("caller_name"), call.get_field("party_size"))
    call.hangup("Thank the caller and let them know we'll text when their table is ready.")
```

---

## Field

`guava.Field` is a task checklist item that instructs the agent to collect a specific piece of structured data through natural conversation.

```python
guava.Field(
    # Identifier used to retrieve the value via get_field() after collection.
    key: str,

    # Natural-language instruction to the LLM about how to collect this value.
    # Use when you do not particularly care how the agent phrases its question.
    description: str = '',

    # Encourages the agent to ask for the field in a particular way.
    # Use instead of description when you want more control over phrasing.
    question: str = '',

    # Controls parsing and validation.
    # "calendar_slot" and "multiple_choice" require either choices or searchable=True.
    field_type: Literal[
        'text', 'date', 'datetime', 'integer', 'multiple_choice', 'calendar_slot'
    ] = 'text',

    # If False, the agent can skip this field if the caller is unwilling to provide it.
    required: bool = True,

    # Static list of valid options for "multiple_choice" and "calendar_slot" fields.
    # Use when the list is small. Large lists should use searchable=True.
    choices: list[str] = [],

    # When True, enables dynamic search for "multiple_choice" and "calendar_slot" fields.
    # The agent calls on_search_query at runtime to find matching options.
    searchable: bool = False,
)
```

**Return types by field_type:**

| `field_type` | Return type |
|---|---|
| `text` | `str` |
| `date` | `dict` with `year`, `month`, `day` keys (all `int`) |
| `datetime` | `dict` with `year`, `month`, `day`, `hour`, `minute` keys |
| `integer` | `int` |
| `multiple_choice` | `str` (guaranteed to match one of the defined choices) |
| `calendar_slot` | ISO-8601 datetime `str` (e.g. `"2026-12-25T16:30"`) |

**Examples:**

```python
# Basic text field
field = guava.Field(
    key="caller_name",
    description="Get the caller's name",
)

# Integer field with a specific question
field = guava.Field(
    key="caller_age",
    question="How old are you?",
    field_type="integer",
)

# Multiple choice with static choices
field = guava.Field(
    key="caller_preference",
    description="Get the caller's preferred fruit",
    field_type="multiple_choice",
    choices=["apple", "banana", "orange"],
    required=False,
)
```

**Searchable fields** (for large option sets):

```python
field = guava.Field(
    key="airport",
    description="Find a suitable airport for the caller",
    field_type="multiple_choice",
    searchable=True,
)

@agent.on_search_query("airport")
def search_airports(call: guava.Call, query: str):
    matching_airports: list[str] = []
    other_airports: list[str] = []

    # Generate matching options based on the caller's natural-language query.
    # The second list is used as fallback when there are no exact matches.
    return matching_airports, other_airports
```

---

## Campaign

Campaigns enable programmatic management of high-volume outbound calling. Use `get_or_create_campaign()` to create or retrieve a campaign by name, upload contacts, define call logic via agent callbacks, and then run the campaign.

```python
from guava.campaigns import get_or_create_campaign, Contact

campaign = get_or_create_campaign(
    "campaign-name",                        # Unique name per organization.
    origin_phone_numbers=[os.environ["GUAVA_AGENT_NUMBER"]],  # Round-robin distribution.
    calling_windows=[
        {"day": day, "start_time": "09:00", "end_time": "17:00"}
        for day in ["monday", "tuesday", "wednesday", "thursday", "friday"]
    ],
    start_date="2026-04-01",       # YYYY-MM-DD format.
    end_date="2026-04-30",         # Optional. YYYY-MM-DD format.
    max_concurrency=3,             # Simultaneous active calls. Default: 1.
    max_attempts=2,                # Retry threshold per contact. Default: 1.
    timezone="America/Los_Angeles",  # IANA format. Default: "America/Los_Angeles".
)

campaign.upload_contacts(
    [
        Contact(phone_number="+15551234567", data={"first_name": "Alice"}),
        Contact(phone_number="+15559876543", data={"first_name": "Bob"}),
    ],
    accepted_terms_of_service=True,
)
```

Contact statuses: `trying`, `completed`, `partially_completed`, `failed`, `do_not_call`.

Use `call.get_variable(key)` inside callbacks to access per-contact `data` fields.

Start serving the campaign (blocks until complete):

```python
agent.outbound_campaign(campaign=campaign).run()
```

**Complete example — political poll:**

```python
import os
import guava
from guava import Agent, Field
from guava.campaigns import get_or_create_campaign, Contact

campaign = get_or_create_campaign(
    "political-poll-q2-2026",
    origin_phone_numbers=[os.environ["GUAVA_AGENT_NUMBER"]],
    calling_windows=[
        {"day": day, "start_time": "09:00", "end_time": "17:00"}
        for day in ["monday", "tuesday", "wednesday", "thursday", "friday"]
    ],
    start_date="2026-04-01",
    max_concurrency=3,
    max_attempts=2,
)

campaign.upload_contacts(
    [
        Contact(phone_number="+15551234567", data={"first_name": "Alice", "district": "District 5"}),
        Contact(phone_number="+15559876543", data={"first_name": "Bob", "district": "District 12"}),
    ],
    accepted_terms_of_service=True,
)

agent = Agent(
    name="Jordan",
    organization="National Opinion Research Center",
    purpose="Conduct a non-partisan political opinion poll.",
)

@agent.on_call_start
def on_call_start(call: guava.Call):
    first_name = call.get_variable("first_name")
    call.reach_person(
        contact_full_name=first_name,
        greeting=(
            f"Hi, is this {first_name}? I'm calling from the National Opinion Research Center "
            "about issues affecting your district. Would you have two minutes to participate?"
        ),
    )

@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str):
    if outcome == "unavailable":
        call.hangup()
    elif outcome == "available":
        first_name = call.get_variable("first_name")
        district = call.get_variable("district")
        call.set_task(
            "political_poll",
            objective=(
                f"Conduct a brief political opinion poll with {first_name} "
                f"in {district}. Be polite and non-partisan."
            ),
            checklist=[
                Field(
                    key="willing_to_participate",
                    description="Whether the respondent agrees to take the poll",
                    field_type="multiple_choice",
                    choices=["yes", "no"],
                ),
                "If they said no, thank them and end the call.",
                Field(
                    key="top_issue",
                    description="Most important issue to the respondent",
                    question=f"What is the most important issue facing {district}?",
                    field_type="multiple_choice",
                    choices=["economy", "healthcare", "education", "housing",
                             "public_safety", "environment", "other"],
                ),
                Field(
                    key="likely_to_vote",
                    description="How likely they are to vote",
                    question="How likely are you to vote in the upcoming election?",
                    field_type="multiple_choice",
                    choices=["very_likely", "likely", "unlikely", "very_unlikely"],
                ),
            ],
        )

@agent.on_task_complete("political_poll")
def on_poll_complete(call: guava.Call):
    call.hangup("Thank them for participating.")

agent.outbound_campaign(campaign=campaign).run()
```

---

## Runner

`guava.Runner` orchestrates multiple agents across multiple channels in a single process.

```python
from guava import Agent, Runner

agent_a = Agent(name="Grace", purpose="You are a helpful voice agent.")
agent_b = Agent(name="Jordan", purpose="You are a helpful voice agent.")

runner = Runner()
runner.listen_phone(agent_a, os.environ["GUAVA_AGENT_NUMBER"])
runner.listen_webrtc(agent_b)
runner.run()
```

**Methods** (all return `self` for chaining):

| Method | Description |
|--------|-------------|
| `listen_phone(agent, agent_number)` | Register an agent to receive inbound calls on a phone number |
| `listen_webrtc(agent, webrtc_code=None)` | Register an agent for WebRTC; auto-generates a code if omitted |
| `listen_sip(agent, sip_code)` | Register an agent to receive inbound SIP calls |
| `attach_campaign(agent, campaign)` | Connect an outbound campaign to an agent |
| `run()` | Start all channels as daemon threads and block until all terminate |

---

## Client

`guava.Client` manages account-level resources.

```python
import guava, os

client = guava.Client(
    api_key=os.environ["GUAVA_API_KEY"],  # Reads from env automatically if omitted.
    base_url=None,  # Optional. Override the API endpoint for testing.
)
```

**Methods:**

| Method | Description |
|--------|-------------|
| `create_sip_agent()` | Generate a SIP code linked to your account for inbound SIP call handling |
| `create_webrtc_agent(ttl=None)` | Generate a WebRTC code for browser-based voice interaction |
| `send_sms(from_number, to_number, message)` | Send an SMS message |

---

## Callbacks

### `on_action_requested` / `on_action`

`on_action_requested` fires when the agent detects a caller intent. Return a `SuggestedAction` with a key to identify which action to run, or `None` if unhandled.

`on_action` fires when Guava executes the action matching a given key.

When a caller utterance is both a question and an action request, Guava calls `on_question` and `on_action_requested` in parallel and picks the most relevant result.

```python
@agent.on_action_requested
def on_action_requested(call: guava.Call, request: str) -> SuggestedAction | None:
    # request: natural-language summary of what the caller wants
    # return: SuggestedAction(key=...) or None
    ...

@agent.on_action("action_key")
def handler(call: guava.Call) -> None:
    # Runs when Guava executes the action with the matching key
    ...
```

**Example — restaurant routing:**

```python
from guava import Agent, SuggestedAction
from guava.helpers.openai import IntentRecognizer

agent = Agent(name="Nova", organization="Thai Palace", purpose="...")

ACTIONS = {
    "reservation": "for handling reservations",
    "waitlist": "additions to the waitlist",
    "delivery": "for takeout orders",
    "hiring": "for people looking for jobs",
    "order_for_pickup": "",
}

intent_recognizer = IntentRecognizer(ACTIONS)

@agent.on_action_requested
def on_action_requested(call: guava.Call, request: str) -> SuggestedAction | None:
    key = intent_recognizer.classify(request)
    return SuggestedAction(key=key) if key else None

@agent.on_action("reservation")
def reservation(call: guava.Call):
    call.set_task(...)

@agent.on_action("waitlist")
def waitlist(call: guava.Call):
    call.set_task(...)
```

---

### `on_question`

Fires when the agent is asked something it cannot answer from context alone. The handler runs in a background thread while the agent stays engaged with the caller. If the lookup takes time, the agent asks for patience.

```python
@agent.on_question
def on_question(call: guava.Call, question: str) -> str:
    # question: natural-language question from the caller
    # return: answer string for the agent to communicate to the caller
    ...
```

**Example:**

```python
from guava import Agent
from guava.helpers.rag import DocumentQA

agent = Agent(name="Nova", organization="Acme Support", purpose="...")
qa = DocumentQA(documents="Product FAQ v2.pdf", namespace="product-faq")

@agent.on_question
def on_question(call: guava.Call, question: str) -> str:
    return qa.ask(question)
```

---

### `on_agent_speech`

Fires whenever the agent produces speech during a call.

```python
@agent.on_agent_speech
def on_agent_speech(call: guava.Call, event: AgentSpeechEvent) -> None:
    ...
```

`AgentSpeechEvent` fields:

| Field | Type | Description |
|-------|------|-------------|
| `utterance` | `str` | The text the agent spoke |
| `interrupted` | `bool` | Whether the caller interrupted the agent |

---

### `on_caller_speech`

Fires whenever the caller's speech is detected. Multiple events may share the same `utterance_id` as transcription is refined in real time — updates append new words or make minor corrections to the same utterance.

```python
@agent.on_caller_speech
def on_caller_speech(call: guava.Call, event: CallerSpeechEvent) -> None:
    ...
```

`CallerSpeechEvent` fields:

| Field | Type | Description |
|-------|------|-------------|
| `event_type` | `str` | Always `"caller-speech"` |
| `utterance` | `str` | The transcribed speech text |
| `utterance_id` | `str \| None` | Identifier consistent across updates to the same utterance |

**Example transcript evolution (same `utterance_id`):**

```
"Hi Grace."
"Hi Grace. I am looking"
"Hi Grace. I am looking to make a reservation"
```

---

## Call Commands

### `set_persona`

Configures the agent's identity and communication style. Deliberately minimal — include the contact's name in `agent_purpose` to help the agent personalize the conversation naturally.

```python
call.set_persona(
    organization_name: str | None = None,  # The organization the agent represents.
    agent_name: str | None = None,         # The agent's first name.
    agent_purpose: str | None = None,      # A sentence describing why the agent is calling.
    voice: str | None = "grace",           # TTS voice: "grace" (southern female) or "jack" (British male).
                                           # Only "grace" supports non-English languages.
)
```

**Example:**

```python
call.set_persona(
    organization_name="Bright Smile Dental",
    agent_name="Grace",
    agent_purpose="You are calling patients to help them schedule and confirm dental appointments",
    voice="grace",
)
```

---

### `send_instruction`

Sends a real-time instruction to the agent without changing the current task. Use it to inject context (e.g. after a database lookup) or nudge agent behavior mid-conversation.

```python
call.send_instruction(instruction: str) -> None
```

Unlike `set_task()`, this preserves the agent's existing objective.

---

### `set_language_mode`

Configures multi-language support. The agent initiates in the primary language and automatically switches when the caller requests or speaks another language.

```python
call.set_language_mode(
    primary: Language = "english",           # Initial conversation language.
    secondary: list[Language] | None = None, # Additional languages the agent can switch to.
)
```

Supported languages: `"english"`, `"spanish"`, `"french"`, `"german"`, `"italian"`.

The `grace` voice includes clones for Spanish, French, German, and Italian. Transcripts are not auto-translated — each turn appears in the language it was spoken.

> **Note:** Non-English languages are not currently supported for HITRUST / PCI-compliant deployments.

**Example:**

```python
call.set_language_mode(primary="english", secondary=["spanish", "french", "german"])
```

---

### `transfer`

Hands the active call off to another phone number or SIP address. The agent notifies the caller before bridging (soft transfer).

```python
call.transfer(
    destination: str,          # Phone number or SIP address.
    instructions: str | None = None,  # What the agent says before bridging.
                                      # Defaults to a generic transfer notification.
)
```

**Example:**

```python
@agent.on_task_complete("collect_issue")
def on_issue_collected(call: guava.Call):
    call.transfer(
        destination="+18005550199",
        instructions="Let the caller know you're transferring them to a service representative.",
    )
```

---

### `hangup`

Hands the agent a final instruction and lets it close the conversation naturally before ending the call. Specific instructions yield better results — mention confirmation numbers, next steps, or appropriate warmth.

```python
call.hangup(final_instructions: str = "")
```

**Example:**

```python
@agent.on_task_complete("collect_order")
def on_order_collected(call: guava.Call):
    call.hangup(
        final_instructions="Thank them for their time, mention the confirmation number, then hang up."
    )
```

---

### `reach_person`

Automates contact verification for outbound calls. The agent greets the answerer, requests the contact by name, handles answering machines and gatekeepers, and fires `on_reach_person` with the outcome. By the time `on_reach_person` fires, the agent has already introduced itself and stated the purpose of the call — do not re-introduce in subsequent tasks.

```python
call.reach_person(
    contact_full_name: str,                         # Required. The person's full name.
    *,
    greeting: str | None = None,                    # Optional custom introduction message.
    outcomes: list[ReachPersonOutcome] | None = None,  # Optional custom outcome routing.
)
```

The outcome is recorded in a `contact_availability` field and passed to `on_reach_person`.

**Example:**

```python
@agent.on_call_start
def on_call_start(call: guava.Call):
    call.reach_person(
        contact_full_name=call.get_variable("contact_name"),
    )

@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str):
    if outcome == "unavailable":
        call.hangup("Leave a brief voicemail asking them to call back.")
    elif outcome == "available":
        call.set_task(
            "main_task",
            checklist=[...],
        )
```

**Common mistake — avoid re-introducing after `reach_person`:**

```python
# WRONG — the agent already introduced itself
@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str):
    if outcome == "available":
        call.set_task("survey", checklist=[
            guava.Say("Hi, this is Grace from Acme Corp, I'm calling about..."),  # redundant
            ...
        ])

# RIGHT — go straight to content
@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str):
    if outcome == "available":
        call.set_task("survey", checklist=[
            guava.Say("I just have a few quick questions for you today."),
            ...
        ])
```

---

### `read_script`

Delivers a verbatim opening statement at the very start of a call, before any LLM involvement or task setup. Use for compliance disclosures, greetings, or any statement requiring exact wording.

```python
call.read_script(script: str)
```

Unlike the `Say` checklist item, `read_script()` fires before any LLM turn.

**Example:**

```python
@agent.on_call_start
def on_call_start(call: guava.Call):
    call.read_script(
        "Hello! This is a courtesy call from Bright Smile Dental. "
        "We're confirming your appointment tomorrow at 2 PM."
    )
    call.set_task(
        "confirm_appointment",
        checklist=[
            guava.Field(key="confirmed", field_type="text",
                        description="Did they confirm the appointment?"),
        ],
    )

@agent.on_task_complete("confirm_appointment")
def on_confirmed(call: guava.Call):
    call.hangup()
```

---

### `add_info`

Provides labeled context data to the agent. Once called, the information persists for the duration of the call and surfaces naturally when relevant. Internally calls `send_instruction` with a formatted message.

```python
call.add_info(
    label: str,  # A label the agent uses to identify the data contextually.
    info: Any,   # The information to pass. Can be a dict, list, string, or any serializable value.
) -> None
```

**Example:**

```python
AMENITIES_INFO = {
    "amenities": [
        "Rooftop pool",
        "Full-service spa",
        "Fitness center",
        "Business center",
        "Complimentary airport shuttle",
    ]
}

@agent.on_call_start
def on_call_start(call: guava.Call):
    call.set_persona(
        organization_name="Oceanfront Hotel",
        agent_name="Grace",
        agent_purpose="You are the head concierge assisting guests with questions and reservations.",
    )
    call.add_info("amenities_details", AMENITIES_INFO)
```

---

### `get_field`

Retrieves a collected field value by key. Can be called at any point after the field has been collected — not only in the completion callback.

```python
call.get_field(field_key: str) -> str | int | dict | None
```

**Return types by field_type:**

| `field_type` | Return value |
|---|---|
| `text` | `str` |
| `date` | `dict` with `year`, `month`, `day` keys (all `int`) |
| `integer` | `int` |
| `multiple_choice` | `str` (guaranteed to match one of the defined choices) |
| `calendar_slot` | ISO-8601 datetime `str` (e.g. `"2026-12-25T16:30"`) |

---

## Helpers

### Intent Helpers

#### `IntentRecognizer`

Classifies a free-text caller utterance into one of your predefined intent labels. Uses `gpt-4o-mini` with low reasoning effort.

```python
from guava.helpers.openai import IntentRecognizer

IntentRecognizer(
    intent_choices: list[str] | dict[str, str],
    client: openai.OpenAI | None = None,
)

recognizer.classify(intent: str) -> str | None
```

**Example:**

```python
import guava
from guava import Agent, SuggestedAction
from guava.helpers.openai import IntentRecognizer

agent = Agent(
    name="Support",
    organization="Acme Corp",
    purpose="Help the caller with their support request.",
)

intent_recognizer = IntentRecognizer(
    ['check order status', 'bill pay', 'anything else']
)

@agent.on_action_requested
def on_action_requested(call: guava.Call, request: str) -> SuggestedAction:
    return SuggestedAction(key=intent_recognizer.classify(request))

@agent.on_action("check order status")
def check_order_status(call: guava.Call):
    call.transfer("+15555555555", "Transfer the caller to the order status team.")

@agent.on_action("bill pay")
def bill_pay(call: guava.Call):
    call.transfer("+15555555555", "Transfer the caller to billing.")

@agent.on_action("anything else")
def anything_else(call: guava.Call):
    call.transfer("+15555555555", "Connect the caller with a live agent.")
```

#### `IntentClarifier`

Returns the subset of choices that could plausibly match a caller's intent, ordered by likelihood. Useful when ambiguity is expected. Uses `gpt-4o-mini` with low reasoning effort.

```python
from guava.helpers.openai import IntentClarifier

IntentClarifier(
    intent_choices: list[str] | dict[str, str],
    client: openai.OpenAI | None = None,
)

clarifier.propose_choices(intent: str) -> list[str]
# Returns multiple matches when ambiguous, one when unambiguous, empty list when no match.
```

**Example:**

```python
import guava
from guava import Agent, SuggestedAction
from guava.helpers.openai import IntentClarifier

agent = Agent(
    name="Scheduler",
    organization="Acme Corp",
    purpose="Help callers manage their appointments.",
)

intent_clarifier = IntentClarifier(
    ['reschedule appointment', 'cancel appointment', 'check appointment time']
)

@agent.on_action_requested
def on_action_requested(call: guava.Call, request: str) -> SuggestedAction:
    matches = intent_clarifier.propose_choices(request)
    if len(matches) == 1:
        # Unambiguous — proceed directly
        return SuggestedAction(key=matches[0])
    elif len(matches) > 1:
        # Ambiguous — route to most likely match; agent will confirm with caller
        return SuggestedAction(key=matches[0], description=f"Caller may have meant one of: {matches}")
    # len == 0: no match, return nothing so the agent keeps listening
```

---

### DocumentQA

Answers caller questions against documents using retrieval-augmented generation (RAG).

**Server mode** (default): Documents are uploaded to Guava's server with server-side question answering. Suitable for simpler scenarios.

**Local mode**: Provide your own vector store and generation model for full control over the RAG pipeline.

```python
from guava.helpers.rag import DocumentQA

DocumentQA(
    store=None,             # VectorStore for local mode. Omit to use server mode.
    documents=None,         # str or list[str] to index.
    ids=None,               # Stable identifiers for upsert/delete operations.
    chunk_size=5000,        # Max characters per chunk (local mode only).
    chunk_overlap=200,      # Overlap between chunks (local mode only).
    instructions=None,      # Additional instructions for the generation model.
    *,
    generation_model=None,  # Required when providing a vector store.
    namespace=None,         # Required in server mode when running multiple concurrent instances.
)

qa.ask(question: str, k: int = 5) -> str
qa.upsert_document(key: str, text: str)   # Add or replace a document by key.
qa.add_document(text: str)                # Add a document without a pre-assigned key.
qa.delete_document(key: str)              # Remove a previously upserted document.
qa.clear()                                # Remove all documents from storage.
```

**Server mode example:**

```python
from guava.helpers.rag import DocumentQA

qa = DocumentQA(documents=[policy_text, faq_text], namespace="policy_faq")
answer = qa.ask("What is the deductible?")
```

**Local mode example (LanceDB + Vertex AI):**

```python
from google import genai
from guava.helpers.lancedb import LanceDBStore
from guava.helpers.vertexai import VertexAIEmbedding, VertexAIGeneration

client = genai.Client(project="my-project", location="us-central1")
store = LanceDBStore("gs://my-bucket/lancedb", embedding_model=VertexAIEmbedding(client=client))
qa = DocumentQA(store=store, generation_model=VertexAIGeneration(client=client))
qa.upsert_document("policy", my_text)
answer = qa.ask("What is the deductible?")
```

**Agent integration example:**

```python
import guava
from guava import Agent
from guava.helpers.rag import DocumentQA

agent = Agent(name="Support", organization="Acme Corp", purpose="Answer customer questions.")
document_qa = DocumentQA(documents=some_text)

@agent.on_question
def on_question(call: guava.Call, question: str) -> str:
    return document_qa.ask(question)
```

**Document management example:**

```python
qa = DocumentQA(
    documents=[policy_v1, faq_v1, terms_v1],
    ids=["policy", "faq", "terms"],
    namespace="insurance",
)

qa.upsert_document("policy", policy_v2)
qa.add_document(new_bulletin_text)
qa.delete_document("terms")
qa.clear()
```

---

### DatetimeFilter

Filters a list of ISO 8601 datetime strings against a natural-language query, returning matches and fallback suggestions. Automatically injects today's date so relative queries like "tomorrow" work without manual date handling. Never hallucinates datetimes — all returned values are guaranteed to exist in the source list.

```python
from guava.helpers.openai import DatetimeFilter

DatetimeFilter(
    source_list: list[str],             # Available datetimes in ISO 8601 format.
    client: openai.OpenAI | None = None,
)

dt_filter.filter(query: str, max_results: int = 5) -> tuple[list[str], list[str]]
# Returns (matches, fallback_suggestions).
# fallback_suggestions is populated when there are no exact matches.
```

**Basic example:**

```python
from guava.helpers.openai import DatetimeFilter

AVAILABLE_SLOTS = [
    "2026-04-16T09:00:00",
    "2026-04-16T10:30:00",
    "2026-04-17T14:00:00",
    "2026-04-18T09:00:00",
]

dt_filter = DatetimeFilter(source_list=AVAILABLE_SLOTS)

matches, suggestions = dt_filter.filter("tomorrow morning", max_results=3)
# matches     == ["2026-04-16T09:00:00", "2026-04-16T10:30:00"]
# suggestions == []  (not needed — matches were found)

matches, suggestions = dt_filter.filter("this Friday at noon", max_results=3)
# matches     == []  (no Friday noon slot exists)
# suggestions == ["2026-04-17T14:00:00", ...]  (nearby alternatives offered)
```

**Integration with a searchable `calendar_slot` Field:**

```python
import guava
from guava import Agent
from guava.helpers.openai import DatetimeFilter

agent = Agent(
    name="Scheduler",
    organization="Acme Corp",
    purpose="Help callers schedule appointments.",
)

datetime_filter = DatetimeFilter(source_list=AVAILABLE_SLOTS)

@agent.on_call_start
def on_call_start(call: guava.Call):
    call.set_task(
        "schedule_appointment",
        checklist=[
            guava.Field(
                key="appointment_time",
                field_type="calendar_slot",
                description="Find a time that works for the caller",
                searchable=True,
            ),
        ],
    )

@agent.on_search_query("appointment_time")
def search_appointments(call: guava.Call, query: str):
    return datetime_filter.filter(query, max_results=3)
```

---

### Vector Stores

Pre-built `VectorStore` implementations for use with `DocumentQA` in local mode.

**Installation:**

```bash
pip install 'gridspace-guava[chromadb]'
pip install 'gridspace-guava[lancedb]'
pip install 'gridspace-guava[pgvector]'
pip install 'gridspace-guava[pinecone]'
```

#### `ChromaVectorStore`

Stores data locally or in-memory. Uses ChromaDB's built-in embedding model by default — no external embedding API required.

```python
from guava.helpers.chromadb import ChromaVectorStore

ChromaVectorStore(
    path: str | None = "./chroma_data",  # Set to None for in-memory/ephemeral storage.
    collection_name: str = "chunks",
    embedding_model: EmbeddingModel | None = None,
)
```

#### `LanceDBStore`

Supports local paths or Google Cloud Storage URIs. Re-indexes automatically when the schema version changes.

```python
from guava.helpers.lancedb import LanceDBStore

LanceDBStore(
    path: str = "./lancedb_data",  # Local path or GCS URI (gs://...).
    table_name: str = "chunks",
    embedding_model: EmbeddingModel,  # Required.
)
```

#### `PgVectorStore`

Connects via a PostgreSQL connection string. Creates necessary extensions and indexes automatically.

```python
from guava.helpers.pgvector import PgVectorStore

PgVectorStore(
    db_url: str,                        # Required. PostgreSQL connection string.
    table_name: str = "guava_chunks",
    embedding_model: EmbeddingModel,    # Required.
)
```

#### `PineconeVectorStore`

Manages embeddings fully through Pinecone's infrastructure. Index creation typically takes 30–60 seconds on first use.

```python
from guava.helpers.pinecone import PineconeVectorStore

PineconeVectorStore(
    api_key: str | None = None,  # Reads from PINECONE_API_KEY env var if omitted.
    index_name: str = "guava-chunks",
    cloud: str = "aws",
    region: str = "us-east-1",
    embedding_model: EmbeddingModel | None = None,  # Defaults to PineconeInferenceEmbedding.
)
```

```python
from guava.helpers.pinecone import PineconeInferenceEmbedding

PineconeInferenceEmbedding(
    pc: Pinecone,                               # Required.
    model: str = "multilingual-e5-large",
    dimensionality: int = 1024,
)
```

**Complete example using multiple backends:**

```python
from guava.helpers.rag import DocumentQA
from guava.helpers.vertexai import VertexAIEmbedding, VertexAIGeneration
from google import genai

client = genai.Client(vertexai=True, project="my-project", location="us-central1")
embedding = VertexAIEmbedding(client=client)   # gemini-embedding-001, 768-dim
generation = VertexAIGeneration(client=client)  # gemini-2.5-flash

# ChromaDB — no external embedding API; persists to disk by default
from guava.helpers.chromadb import ChromaVectorStore
store = ChromaVectorStore()                     # path="./chroma_data"
store = ChromaVectorStore(path=None)            # in-memory

qa = DocumentQA(store=store, generation_model=generation, documents=[doc1, doc2])
answer = qa.ask("What is the deductible?")

# LanceDB — local path or GCS URI
from guava.helpers.lancedb import LanceDBStore
store = LanceDBStore("./lancedb_data", embedding_model=embedding)
store = LanceDBStore("gs://my-bucket/lancedb", embedding_model=embedding)  # GCS

qa = DocumentQA(store=store, generation_model=generation, documents=[doc1, doc2])

# pgvector — table and indexes created automatically
from guava.helpers.pgvector import PgVectorStore
store = PgVectorStore(
    db_url="postgresql://user:password@localhost:5432/mydb",
    embedding_model=embedding,
)
qa = DocumentQA(store=store, generation_model=generation, documents=[doc1, doc2])

# Pinecone — set PINECONE_API_KEY; index and embeddings fully managed
from guava.helpers.pinecone import PineconeVectorStore
store = PineconeVectorStore()                   # index_name="guava-chunks"

qa = DocumentQA(store=store, generation_model=generation, documents=[doc1, doc2])
answer = qa.ask("What is the deductible?")
```
