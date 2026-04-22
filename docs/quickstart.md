# Quickstart

The recommended approach for building Guava voice agents is the Guava CLI, which sets up projects and installs necessary components. Alternatively, direct SDK installation is available.

## Account Setup

Begin by registering at [app.goguava.ai](https://app.goguava.ai).

## CLI Installation

**Script-based (macOS/Linux):**

```bash
curl -fsSL https://storage.googleapis.com/gridspace-guava-cli/cli/install.sh | sh
```

**Homebrew (macOS):**

```bash
brew tap goguava-ai/tap
brew install goguava-ai/tap/guava
```

## Authentication

```bash
guava login
```

## Create an Agent

Bootstrap a new project with starter code:

```bash
guava create my-agent
```

## Optional: Clone the Starter Repository

Clone the Guava starter materials containing API documentation and examples sized for AI coding assistants:

```bash
git clone https://github.com/goguava-ai/guava-starter.git my-agent/guava-starter
```

## Deploy

```bash
guava deploy up ./my-agent
```

Monitor progress through the Deployments dashboard and view calls in Conversations.

---

# SDK Installation (Without CLI)

If you prefer to skip the CLI, you can install the SDK directly.

## Install the SDK

**pip:**

```bash
pip install guava-sdk
```

**uv:**

```bash
uv add guava-sdk
```

**poetry:**

```bash
poetry add guava-sdk
```

## Set Environment Variables

```bash
export GUAVA_API_KEY="gva-..."         # Set to your API key.
export GUAVA_AGENT_NUMBER="+15551234567" # Set to your purchased number.
```

Your API key is available from the API Keys dashboard. `GUAVA_AGENT_NUMBER` is a phone number you purchase through Guava.

## Optional: Clone the Starter Repository

```bash
git clone https://github.com/goguava-ai/guava-starter.git guava-starter
```

## Run an Example

The SDK includes pre-built examples you can run directly.

**Outbound scheduling call** — your agent will call the number you provide:

```bash
python -m guava.examples.scheduling_outbound +1... "John Doe"
```

**Inbound restaurant waitlist** — dial your agent's number while the script is running:

```bash
python -m guava.examples.restaurant_waitlist
```

---

# Example: Inbound Call with RAG

This example builds an inbound voice agent for a property insurance company. Callers can ask questions about their policy, and the agent answers using a document knowledge base.

## Define the Agent

```python
import guava

agent = guava.Agent(
    organization="Harper Valley Property Insurance",
    purpose="Answer questions regarding property insurance policy until there are no more questions",
)
```

## Set Up DocumentQA

`DocumentQA` is a built-in RAG helper. You can substitute any knowledge base system you prefer.

```python
from guava.helpers.rag import DocumentQA
from guava.examples.example_data import PROPERTY_INSURANCE_POLICY

document_qa = DocumentQA(documents=PROPERTY_INSURANCE_POLICY)
```

## Handle Questions with `on_question`

When the agent is asked something it cannot answer from context alone, it invokes the `on_question` callback. The agent remains fully responsive during the lookup — it continues listening and engaging with the caller while waiting for your response.

```python
@agent.on_question
def on_question(call: guava.Call, question: str) -> str:
    return document_qa.ask(question)
```

## Start the Agent

Guava does not require a public web server to receive inbound calls. All agents can run behind firewalls and NATs.

```python
# Attach your agent to a phone number. Call your agent's number to talk to it.
agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

# Receive a WebRTC link to talk to your agent in the browser.
agent.listen_webrtc()

# Talk to your agent using your local audio device.
agent.call_local()
```

## Complete Example

```python
import logging
import os
import guava
import argparse

from guava.helpers.rag import DocumentQA
from guava import logging_utils, Agent
from guava.examples.example_data import PROPERTY_INSURANCE_POLICY

logger = logging.getLogger("guava.examples.property_insurance")

agent = Agent(
    organization="Harper Valley Property Insurance",
    purpose="Answer questions regarding property insurance policy until there are no more questions",
)

# Built-in knowledge base helper. You can use any RAG system you prefer.
document_qa = DocumentQA(documents=PROPERTY_INSURANCE_POLICY)

# When the agent is asked a question it cannot answer, it invokes on_question.
@agent.on_question
def on_question(call: guava.Call, question: str) -> str:
    # Forward the question to the knowledge base and return the answer.
    answer = document_qa.ask(question)
    logger.info("RAG answer: %s", answer)
    return answer

if __name__ == "__main__":
    logging_utils.configure_logging()

    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--phone", action="store_true", help="Listen for phone calls.")
    group.add_argument("--webrtc", action="store_true", help="Create a WebRTC code.")
    group.add_argument("--local", action="store_true", help="Start a local call.")
    args = parser.parse_args()

    if args.phone:
        agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
    elif args.webrtc:
        agent.listen_webrtc()
    else:
        agent.call_local()
```

---

# Example: Inbound Call with Form Filling

This example builds an inbound voice agent for a restaurant waitlist. The agent collects caller information conversationally using structured fields.

## Define the Agent

`guava.Agent` is the starting point for building Guava agents.

```python
import guava

agent = guava.Agent(
    name="Mia",
    organization="Thai Palace",
    purpose="Helping callers join the restaurant waitlist",
)
```

## Accept or Reject Calls

`on_call_received` fires before the call starts and gives you a chance to accept or reject based on caller info.

```python
@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()
```

## Set Up a Task with Fields

`on_call_start` fires at the beginning of every accepted call. Use `set_task` to give the agent a structured checklist.

The checklist can mix `Field` objects (typed, named values the agent extracts) with plain strings (freeform instructions the agent follows). The agent gathers each piece of information conversationally and automatically moves on when all fields are filled.

```python
@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
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
```

## Handle Task Completion

`on_task_complete` fires once every field in the checklist is collected.

```python
@agent.on_task_complete("waitlist")
def on_waitlist_done(call: guava.Call) -> None:
    logger.info(
        "Added %s, party of %d, to waitlist.",
        call.get_field("caller_name"),
        call.get_field("party_size"),
    )
    call.hangup("Thank the caller and let them know we'll text when their table is ready.")
```

## Start the Agent

```python
# Attach your agent to a phone number. Call your agent's number to talk to it.
agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

# Receive a WebRTC link to talk to your agent in the browser.
agent.listen_webrtc()

# Talk to your agent using your local audio device.
agent.call_local()
```

## Complete Example

```python
import os
import guava
import logging
import argparse
from guava import logging_utils

logger = logging.getLogger("thai_palace")

agent = guava.Agent(
    name="Mia",
    organization="Thai Palace",
    purpose="Helping callers join the restaurant waitlist",
)

@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()

@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
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
def on_waitlist_done(call: guava.Call) -> None:
    logger.info(
        "Added %s, party of %d, to waitlist.",
        call.get_field("caller_name"),
        call.get_field("party_size"),
    )
    call.hangup("Thank the caller and let them know we'll text when their table is ready.")

if __name__ == "__main__":
    logging_utils.configure_logging()

    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--phone", action="store_true", help="Listen for phone calls.")
    group.add_argument("--webrtc", action="store_true", help="Create a WebRTC code.")
    group.add_argument("--local", action="store_true", help="Start a local call.")
    args = parser.parse_args()

    if args.phone:
        agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
    elif args.webrtc:
        agent.listen_webrtc()
    else:
        agent.call_local()
```
