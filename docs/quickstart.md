# Quickstart

Welcome to Guava, a voice agent platform created exclusively for developers. Guava allows developers to deliver reliable voice agents that integrate seamlessly with existing agentic AI systems.

The primary interface for using Guava is a Python SDK.

### Installation / Setup

> NOTE
> Prerequisites

- Python >= 3.10
- A Guava API Key and Phone Number

1. Install the Python SDK using your preferred method.

*Method 1: pip*

```
$ pip install gridspace-guava --extra-index-url https://guava-pypi.gridspace.com

```

*Method 2: uv astral*

```
$ uv add gridspace-guava --index guava=https://guava-pypi.gridspace.com

```

*Method 3: poetry*

```
$ poetry source add --priority=explicit guava https://guava-pypi.gridspace.com
$ poetry add --source guava gridspace-guava

```

2. Set your environment variables.

```
$ export GUAVA_API_KEY="..."
$ export GUAVA_AGENT_NUMBER="..."

```

3. You’re ready.

## Running an Example

Examples can be found in the `guava.examples` submodule. Running one starts a voice conversation through a phone or webrtc session.

### Outbound Phone Call

```
$ python -m guava.examples.scheduling_outbound +1... # Use your phone number here and your agent will call you.

```

### Inbound Phone Call

```
$ python -m guava.examples.thai_palace
$ # Now dial your agent's number while the script is running.

```

### Inbound WebRTC

```
$ python -m guava.tools.create_webrtc_agent # Create a WebRTC agent code.
$ python -m guava.examples.inbound_webrtc grtc-... # Start the listener
$ # Go to https://guava-dev.gridspace.com/debug-webrtc and call the agent.

```

## Example Walkthroughs

### Outbound Call with Appointment Scheduling

In this example, we'll be making outbound calls to schedule appointments for a fictional dental office. You can run the completed version of this example from the SDK.

```
$ python -m guava.examples.scheduling_outbound +1... # Use your phone number here and your agent will call you.

```

We create a new CallController subclass to manage the call:

```
class SchedulingController(guava.CallController):
    def __init__(self, patient_name):
        super().__init__()
        self.datetime_filter = DatetimeFilter(source_list=MOCK_APPOINTMENTS)
        self._intended_recipient = patient_name
        self.set_persona(
            organization_name="Bright Smile Dental",
            agent_name="Grace",
            agent_purpose=f'You are calling {self._intended_recipient} to help them schedule a dental appointment',
        )
        self.reach_person(
            contact_full_name=self._intended_recipient,
            on_success=self.schedule_recipient,
            on_failure=self.recipient_unavailable,
        )

```

Here, we use the `DatetimeFilter` class, which uses an external LLM call to find potential times based on user input.

> NOTE
> Note
>
> In a production use case, you would likely replace DatetimeFilter with your own scheduling backend. It's provided here as an example to get you started quickly.

We also use the `reach_person` convenience function to confirm that we are talking to the intended recipient of the call. Once the callee has been confirmed, we transition to the `schedule_recipient` function.

```
    def schedule_recipient(self):
        self.set_task(
            checklist=[
                # Use guava.Say to instruct the agent to repeat a line verbatim.
                guava.Say("Let me look to see what appointment times we have available."),
                guava.Field(
                    key="appointment_time",
                    field_type='calendar_slot',
                    description="Find a time that works for the caller",
                    choice_generator=self.appointment_time_filter
                ),
                guava.Say("Your appointment has been confirmed! Have a nice day.")
            ],
            on_complete=self.end_call,
        )

```

The `Field` checklist item instructs the voice bot to negotiate with the patient to pick a calendar slot for their appointment.

The `choice_generator` function is a function that we implement which takes in a natural language description of what times are preferable to the patient. For example, they might say "Tuesdays and Fridays work best". The `choice_generator` is then free to use that input in conjunction with any external data sources and models to suggest some dates and times.

```
    def appointment_time_filter(self, query: str):
        return self.datetime_filter.filter(query, max_results=3)

```

In this example, we use the `DatetimeFilter` helper class, intialized with a list of hardcoded times.

The full outbound scheduling is show below.

```
import argparse
import logging
import guava
import os

from guava.examples.mock_appointments import MOCK_APPOINTMENTS
from guava.helpers.openai import DatetimeFilter

selected_time = None

class SchedulingController(guava.CallController):
    def __init__(self, patient_name):
        super().__init__()
        self.datetime_filter = DatetimeFilter(source_list=MOCK_APPOINTMENTS)
        self._intended_recipient = patient_name
        self.set_persona(
            organization_name="Bright Smile Dental",
            agent_name="Grace",
            agent_purpose=f'You are calling {self._intended_recipient} to help them schedule a dental appointment',
        )
        self.reach_person(
            contact_full_name=self._intended_recipient,
            on_success=self.schedule_recipient,
            on_failure=self.recipient_unavailable,
        )

    def schedule_recipient(self):
        self.set_task(
            checklist=[
                guava.Say("Let me look to see what appointment times we have available."),
                guava.Field(
                    key="appointment_time",
                    field_type='calendar_slot',
                    description="Find a time that works for the caller",
                    choice_generator=self.appointment_time_filter
                ),
                guava.Say("Your appointment has been confirmed! Have a nice day.")
            ],
            on_complete=self.end_call,
        )

    def appointment_time_filter(self, query: str):
        return self.datetime_filter.filter(query, max_results=3)

    def end_call(self):
        global selected_time
        selected_time = self.get_field("appointment_time")
        self.hangup(final_instructions="Thank them for their time and hang up the call.")

    def recipient_unavailable(self):
        self.hangup(final_instructions="Apologize for your mistake and hang up the call.")

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("phone", type=str, help="Phone number to call.")
    args = parser.parse_args()

    client = guava.Client()
    client.create_outbound(
        from_number=os.environ['GUAVA_AGENT_NUMBER'],
        to_number=args.phone,
        call_controller=SchedulingController(patient_name="Benjamin Buttons"),
    )
    if selected_time:
        client.send_sms(
            from_number=os.environ['GUAVA_AGENT_NUMBER'],
            to_number=args.phone,
            message=f"Your appointment has been confirmed for {selected_time}"
        )

```

### Outbound Sales Call with RAG

In this example, we will call a potential customer for a fictional real estate company and answer their questions by referencing a knowledge base.

```
class InsuranceCallController(guava.CallController):
  def __init__(self):
    super().__init__()

  @override
  def on_question(self, question: str) -> str:
    ...

```

The first step is to define a `CallController` subclass. The `CallController` implements callback functions that steer the voice experience in real-time during the call. You can think of Guava as providing the Agent, and your `CallController` as the expert coach, whispering in the Agent's ear as they handle the call.

Since we want our bot to provide truthful answers to the customer's questions, the Agent will invoke the `on_question` function any time the user asks something that can't be inferred from context alone. You'll receive the question in natural language, and you are then free to use any technologies and tools at your disposal to return the answer. The Agent will continue to be responsive and attentive to the conversation while waiting for your response, so you are not latency-constrained in your `on_question` implementation.

```
from guava.examples.example_data import PROPERTY_INSURANCE_POLICY
from guava.helpers.openai import DocumentQA

class InsuranceCallController(guava.CallController):
  def __init__(self):
    super().__init__()
    self.document_qa = DocumentQA("harper-valley-property-insurance", PROPERTY_INSURANCE_POLICY)

  @override
  def on_question(self, question: str) -> str:
    return self.document_qa.ask(question)

```

The Guava SDK provides helpers for common patterns, including a `DocumentQA` class, which implements RAG using OpenAI's vector store API. In your own programs, you are free to use any models or providers to handle the Guava callbacks.

Next, we need to give the Agent some information about the job to be done on this call. Unlike some AI platforms, Guava discourages long system prompts that attempt to cover every possible scenario, in favor of short contextual directions. We'll provide that using the `set_persona` and `set_task` functions.

```
class InsuranceCallController(guava.CallController):
  def __init__(self):
    super().__init__()
    self.document_qa = DocumentQA("harper-valley-property-insurance", PROPERTY_INSURANCE_POLICY)
    self.set_persona(organization_name="Harper Valley Property Insurance")
    self.set_task(
      '''
      You are making an outbound call to a potential customer.
      Your task is to answer questions regarding property insurance
      policy until there are no more questions.
      '''
    )

```

The `set_persona` function lets the Agent know what organization it is representing on the call. The `set_task` function gives the Agent a brief summary of its current objective. As the conversation progresses, we may call `set_task` again to change our short-term objective, for example to authenticate the user or fill out a form. We'll see other examples of call steering in later examples.

With all that in place, it's time to start talking!

```
if __name__ == "__main__":
  guava.Client().create_outbound(
    from_number=os.environ['GUAVA_AGENT_NUMBER'],
    to_number="+1...", # Your phone number goes here.
    call_controller=InsuranceCallController(),
  )

```

The `guava.Client()` constructor will open a new control websocket to the Guava API server, and `create_outbound` will initiate an outbound phone call. To test our Agent, we just run the script, making sure that our API key and agent number variables are set:

```
$ export GUAVA_API_KEY="..."
$ export GUAVA_AGENT_NUMBER="..."
$ python ./insurance_example.py

```

The full example code is shown below.

insurance_example.py

```
import guava
import os
import logging

from typing_extensions import override
from guava.examples.example_data import PROPERTY_INSURANCE_POLICY
from guava.helpers.openai import DocumentQA

# Print logs at the INFO level.
logging.basicConfig(level=logging.INFO)

class InsuranceCallController(guava.CallController):
  def __init__(self):
    super().__init__()
    # Load in a QA system based off a long and complex property insurance document.
    self.document_qa = DocumentQA("harper-valley-property-insurance", PROPERTY_INSURANCE_POLICY)
    self.set_persona(organization_name="Harper Valley Property Insurance")
    self.set_task("You are making an outbound call to a potential customer. Your task is to answer questions regarding property insurance policy until there are no more questions.")

  @override
  def on_question(self, question: str) -> str:
    # Replace with your fancy RAG system.
    return self.document_qa.ask(question)

if __name__ == "__main__":
  guava.Client().create_outbound(
    from_number=os.environ['GUAVA_AGENT_NUMBER'],
    to_number="+1...", # Your phone number goes here.
    call_controller=InsuranceCallController(),
  )

```

### Inbound Reservation Call with Intent Recognition and Form Filling

In this example, we will walk through how to set up an inbound call listener for a restaurant. When a caller phones in to make a reservation, the Agent listens for the caller’s intent, routes it to your `CallController`, and responds appropriately. Let's start by defining a new `CallController` subclass.

```
class RestaurantReservationCallController(guava.CallController):
  def __init__(self):
    super().__init__()

```

When the Agent detects an action or intent expressed by the caller, it needs a way to notify our `RestaurantReservationCallController` appropriately based on what the caller is trying to do. To support this, the Agent invokes the `on_intent` method whenever a caller intent is detected.

The detected intent is passed to `on_intent` in natural language, giving you the flexibility to use any tools, services, or logic needed to determine the next steps. While this processing occurs, the Agent remains engaged in the conversation with the caller, ensuring the caller experience stays responsive.

How can we set things up such that our `RestaurantReservationCallController` is able to process downstream logic on a select set of intents that the Agent detects?

```
from guava.helpers.openai import IntentRecognizer

```

The Guava SDK provides a helper `IntentRecognizer` class, an LLM-based classifier. The SDK reference for `IntentRecognizer` can be found here.

```
class RestaurantReservationCallController(guava.CallController):
  def __init__(self):
    super().__init__()
    self.intent_recognizer = IntentRecognizer(["making a reservation", "anything else"])

  @override
  def on_intent(self, intent: str):
    choice = self.intent_recognizer.classify(intent)
    if choice == "making a reservation":
      ...
    else:
      ...

```

We initialize the intent recognizer in the constructor by providing a list of intents we want to classify. When an intent is detected and matched, we handle it in the `on_intent` callback, where we can take action based on the matched intent. The `classify` method returns the most likely intent from the list provided during initialization.

With intent classification in place, we will use the `set_persona` and `set_task` methods to give the Agent its own background and guide its behavior, both at the start of the call and whenever a caller’s intent is detected.

```
class RestaurantReservationCallController(guava.CallController):
  def __init__(self):
    super().__init__()
    self.intent_recognizer = IntentRecognizer(["making a reservation", "anything else"])
    self.set_persona(organization_name="Thai Palace")
    self.make_reservation()

  def make_reservation(self):
    self.set_task(
      objective="You are a virtual assistant for a restaurant called Thai Palace. Your job is to add callers to a reservation list.",
      checklist=[
        guava.Field(
          key="caller_name",
          field_type="text",
          description="The name to be added to the waitlist"
        ),
        guava.Field(
          key="party_size",
          field_type="integer",
          description="The number of people attending",
        ),
        guava.Field(
          key="phone_number",
          field_type="text",
          description="Phone number to text when the table is ready",
        ),
        "Read the phone number back to the caller to make sure you got it right.",
      ],
      on_complete=self.hangup,
    )

  @override
  def on_intent(self, intent: str):
    choice = self.intent_recognizer.classify(intent)
    if choice == "making a reservation":
      self.make_reservation()
    else:
      self.set_task(
        checklist=["Tell the caller that we only handle restaurant reservation at this number."],
        on_complete=self.make_reservation,
      )

```

The `set_persona` method establishes that the agent is representing the Thai Palace restaurant for these calls.

Beyond defining the Agent’s current objective through the `objective` argument, the `set_task` method also allows you to supply a `checklist` (a structured list of to-do items the agent must complete) and an `on_complete` callback (invoked once all checklist items have been satisfied).

In this reservation example, we need to collect a few pieces of information from the caller: their name, the number of guests, and a phone number for the reservation. To gather this information, we populate the `checklist` with `guava.Field(...)` entries, one for each required detail. We can also include natural language in the form of a plain Python string in the `checklist` to provide the Agent with more flexible, high-level guidance on how to conduct the conversation.

Once all `checklist` items have been completed, we pass the `hangup` method (provided by the Guava SDK as part of the `CallController` interface) as the `on_complete` callback, allowing the Agent to gracefully end the call when the reservation making process is finished.

For more details on `set_task` and the supported checklist item types, refer to the SDK reference here.

```
class RestaurantReservationCallController(guava.CallController):
  def __init__(self):
    super().__init__()
    self.intent_recognizer = IntentRecognizer(["making a reservation", "anything else"])
    self.set_persona(organization_name="Thai Palace")
    self.make_reservation()
    self.accept_call()

```

Unlike the outbound example, inbound calls require an explicit decision about how to handle incoming callers. While the `Client` waits and listens for inbound calls, our `RestaurantReservationCallController` is responsible for deciding whether a call should be accepted or rejected. This is done using the `accept_call()` method, which allows the Agent to answer and begin handling the call. In some cases, you may instead choose to call `reject_call()` (for example, if the incoming number is on a blacklist or does not meet your acceptance criteria).

With all that in place, let's set up our `Client` to start listening for inbound calls.

```
if __name__ == "__main__":
  guava.Client().listen_inbound(
    agent_number=os.environ["GUAVA_AGENT_NUMBER"],
    controller_class=RestaurantReservationCallController,
  )

```

The `guava.Client()` constructor will open a new control websocket to the Guava API server, and `listen_inbound` will start listening for inbound calls. To test our Agent, we just run the script, making sure that our API key and agent number variables are set:

```
$ export GUAVA_API_KEY="..."
$ export GUAVA_AGENT_NUMBER="..."
$ python ./restaurant_example.py

```

The full `restaurant_example.py` file is shown below.

```
# restaurant_example.py

import logging
import guava
import os
from typing_extensions import override
from guava.helpers.openai import IntentRecognizer

# Print logs at the INFO level.
logging.basicConfig(level=logging.INFO)

class RestaurantReservationCallController(guava.CallController):
  def __init__(self):
    super().__init__()
    self.intent_recognizer = IntentRecognizer(["making a reservation", "anything else"])
    self.set_persona(organization_name="Thai Palace")
    self.make_reservation()
    self.accept_call()

  def make_reservation(self):
    self.set_task(
      objective="You are a virtual assistant for a restaurant called Thai Palace. Your job is to add callers to a reservation list.",
      checklist=[
        guava.Field(
          key="caller_name",
          field_type="text",
          description="The name to be added to the waitlist"
        ),
        guava.Field(
          key="party_size",
          field_type="integer",
          description="The number of people attending",
        ),
        guava.Field(
          key="phone_number",
          field_type="text",
          description="Phone number to text when the table is ready",
        ),
        "Read the phone number back to the caller to make sure you got it right.",
      ],
      on_complete=self.hangup,
    )

  @override
  def on_intent(self, intent: str):
    choice = self.intent_recognizer.classify(intent)
    if choice == "making a reservation":
      self.make_reservation()
    else:
      self.set_task(
        checklist=["Tell the caller that we only handle restaurant reservation at this number."],
        on_complete=self.make_reservation,
      )

if __name__ == "__main__":
  guava.Client().listen_inbound(
    agent_number=os.environ["GUAVA_AGENT_NUMBER"],
    controller_class=RestaurantReservationCallController,
  )

```
