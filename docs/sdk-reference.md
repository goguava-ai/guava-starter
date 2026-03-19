# SDK Reference

### 1. SDK Architecture Overview

The Guava Python SDK uses a controller-based architecture that separates call behavior from call execution. Developers define how a voice agent behaves by subclassing `guava.CallController` and overriding lifecycle methods to implement custom call flows, while the `guava.Client` is responsible for starting and managing inbound or outbound calls using that controller. During a call, behavior is guided through tasks set via `set_task()`, which accepts structured task types (`Field`, `Say`, and plain Python strings) to control what the agent says, what information it must collect, and where the LLM has flexibility, enabling precise, composable control of voice interactions without prompt bloat.

### 2. CallController (The Heart of the SDK)

*Defines the behavior of a voice agent during a call.Developers create custom call flows by subclassing it, setting the agent’s task, and overriding lifecycle methods.*

#### 2.1 Creating a Custom CallController

```
import guava

class DentalOfficeCallController(guava.CallController):
  # Create your own custom CallController!
  pass

```

#### 2.2 `set_task(...)`

*The powerhouse function of the SDK. Defines the current objective for your voice agent.*

```
# Method Reference
def set_task(
  # Provides the voice agent with the overall goal for this task.
  objective: str="",

  # Provides the voice agent with a list of checklist items of Types.
  checklist: list[Field | Say | str] | None = None,

  # A callback function to trigger once the above checklist items are fulfilled.
  on_complete: Callable = lambda: None,
)
# Note: At least one of `objective` or `checklist` should be provided.

# Example
class DentalOfficeCallController(guava.CallController):
  def __init__(self):
    super().__init__()
    self.set_task(
      objective="Your task is to collect basic information from the caller",
      checklist=[
        guava.Say("Let's start with some basic patient intake"),
        guava.Field(
          key="caller_name",
          description="What is your name?",
          field_type="text",
        ),
        guava.Field(
          key="caller_age",
          description="how old are you?",
          field_type="integer",
        ),
        "Tell the caller you'll update your records",
      ],
      on_complete=self.update_records,
    )

  def update_records(self):
    ...

```

The `set_task()` method takes in 3 arguments:

- `objective`
- `checklist`
- `on_complete`

The `checklist` argument of the `set_task()` method takes in a list of checklist items that you provide to your voice agent to accomplish for that task. Each checklist item can be one of the following 3 types:

| Type | Purpose |
| `guava.Field` | Collect structured information from the caller |
| `guava.Say` | Speak verbatim text |
| `str` | Provide flexible instructions to the LLM |

#### 2.2.1 `Field`

*A declarative way to collect structured data from a caller. Use*`guava.Field`*when you need a specific value filled in by the caller.*

```
# Constructor & Properties
guava.Field(
  item_type: Literal["field"] = "field",
  key: str,
  description: str,
  field_type: Literal["text", "date", "integer"],
  required: bool = True,
)

# Example
field = guava.Field(
  key="caller_name",
  description="What is your name?",
  field_type="text",
  required=True,
)

```

#### 2.2.2 `Say`

*Forces the voice agent to say the text verbatim.*

```
# Constructor & Properties
guava.Say(
  item_type: Literal["say"] = "say",
  statement: str,
  key: str | None,
)

# Example
say = guava.Say("Hello, this is Grace speaking. How are you doing today?")

```

#### 2.2.3 `str` (Plain Python String)

*High-level instructions that give your voice agent freedom in how it responds.*

#### 2.3 Lifecycle Methods (Override Points)

*Override methods of the `CallController` like `on_intent()` and `on_question()` in your subclass to better fit your needs.*

```
class DentalOfficeCallController(guava.CallController):
  def __init__(self):
    super().__init__()
    # other initilizations
    ...

  @override
  def on_intent(self, intent: str):
    ...

  @override
  def on_question(self, question: str):
    ...

```

#### 2.3.1 Subclass Override: `on_intent(...)`

*Called when your voice agent detects an action intended by the human caller.*

```
# Example
from guava.helpers.openai import IntentRecognizer

class RestaurantCallController(guava.CallController):
  def __init__(self):
    super().__init__()
    self.intents = ["wait time inquiry", "delivery", "pick-up"]
    # More info about IntentRecognizer (i.e. helpers) in Section 4.1
    self.intent_recognizer = IntentRecognizer(self.intents)

  @override
  def on_intent(self, intent: str):
      choice = self.intent_recognizer.classify(intent)
      if choice == "wait time inquiry":
        pass
      elif choice == "delivery":
        pass
      elif choice == "pick-up":
        pass

```

#### 2.3.2 Subclass Override: `on_question(...)`

*Called when your voice agent detects a question asked by the human caller.*

```
# Example
from guava.helpers.openai import DocumentQA
from documents import some_text

class RestaurantCallController(guava.CallController):
  def __init__(self):
    super().__init__()
    # More info about DocumentQA (i.e. helpers) in Section 4.2
    self.document_qa = DocumentQA("my-restaurant-faq", some_text)

  @override
  def on_question(self, question: str):
    answer = self.document_qa.ask(question)
    return answer

```

#### 2.4 `get_field(...)`

*Retrieve your wanted fields.*

```
# Method Reference
def get_field(
  # The guava.Field 'key' that was provided to the set_task(...) function.
  field_key: str,
)

# Example
class DentalOfficeCallController(guava.CallController):
  def __init__(self):
    super().__init__()
    self.set_task(
      objective="Your task is to collect basic information from the caller",
      checklist=[
        guava.Say("Let's start with some basic patient intake"),
        guava.Field(
          key="caller_name",
          description="What is your name?",
          field_type="text",
        ),
        guava.Field(
          key="caller_age",
          description="how old are you?",
          field_type="integer",
        ),
        "Tell the caller you'll update your records",
      ],
      on_complete=self.update_records,
    )

  def update_records(self):
    patient_name = self.get_field("caller_name")
    patient_age = self.get_field("caller_age")
...

```

#### 2.5 `set_persona(...)`

*Give your voice agent a persona.*

```
# Method Reference
def set_persona(
  organization_name: str | None = None,
  agent_name: str | None = None,
  agent_purpose: str | None = None,
)

# Example
class RestaurantCallController(guava.CallController):
  def __init__(self):
    super().__init__()
    self.set_persona(
      organization_name="Gridspace Bar and Grill",
      agent_name="Grace",
      agent_purpose="You're a voice agent acting as a hostess at a restaurant. Your main job is to answer questions from callers about the restaurant".",
    )
    self.set_task(
      "Introduce yourself. Figure out why the caller is calling."
    )

```

#### 2.6 `read_script(...)`

*Give your voice agent a script to say verbatim at the start of your call.*

```
# Method Reference
def read_script(
  script: str,
)

# Example
class RestaurantCallController(guava.CallController):
  def __init__(self):
    super().__init__()
    self.read_script("Hi, thank you for calling. How can I help you today?")
    self.accept_call()

```

#### 2.7 (For inbound calls) `accept_call()`

*Accept an inbound call in your*`CallController`*.(Recommended) Use*`accept_call()`*at the end of your constructor.*

```
# Method Reference
def accept_call()

# Example
class RestaurantCallController(guava.CallController):
  def __init__(self):
    super().__init__()
    self.accept_call()

```

#### 2.8 (For inbound calls) `reject_call()`

*Reject an inbound call in your*`CallController`*.(Recommended) Use*`accept_call()`*at the end of your constructor.*

```
# Method Reference
def reject_call()

# Example
class RestaurantCallController(guava.CallController):
  def __init__(self):
    super().__init__()
    if (CALLEE_NUMBER in BLACKLISTED_NUMBERS):
      self.reject_call()
    else:
      self.accept_call()

```

#### 2.9 `hangup(...)`

*Instructs your voice agent to initiate a soft hangup process.*

```
# Method Reference
def hangup(
  final_instructions: str='Hang up the call.',
)

# Example
class RestaurantCallController(guava.CallController):
  def __init__(self):
    super().__init__()
    self.get_customer_info()

  def get_customer_info(self):
    self.set_task(
      checklist=[...],
      on_complete=self.hangup,
    )

```

### 3. Client (Starting Calls)

*With your custom*`CallController`*, use the*`Client`*to start making real calls.The*`Client`*will connect to the Gridspace dialog-managing servers.*

#### 3.1 Create a Client

```
# Constructor & Properties
guava.Client(
  api_key: str | None = None,
  base_url: str | None = None,
)

# Example
client = guava.Client()

```

#### 3.2 Start an Outbound Call

```
# Method Reference
guava.Client().create_outbound(
  from_number: str | None = None,
  to_number: str,
  call_controller: CallController | None = None,
)

# Example
number_to_call = "+16501234567"
controller = RestaurantCallController()
client.create_outbound(
  from_number=os.environ["GUAVA_AGENT_NUMBER"],
  to_number=number_to_call,
  call_controller=controller,
)

```

#### 3.3 Handle Inbound Calls

```
# Function Arguments
guava.Client().listen_inbound(
  agent_number: str | None = None,
  webrtc_code: str | None = None,
  controller_class: Type[U],
)

# Example
client.listen_inbound(
  agent_number=os.environ["GUAVA_AGENT_NUMBER"],
  controller_class=RestaurantCallController, # initialized in listen_inbound()
)

```

### 4. [Optional] Helpers

*Helper classes that the CallController can use to help with the flow of the conversation.*

#### 4.1 IntentRecognizer

*Classify caller intent during a conversation.*

```
# Constructor & Properties
guava.helpers.openai.IntentRecognizer(
  intent_choices: list[str],
  client: openai.OpenAI | None = None,
)

# Class Method Reference
# classify: Choose one of the `intent_choices` provided to the IntentRecognizer
def classify(
  intent: str,
) -> str

# Example
from guava.helpers.openai import IntentRecognizer
intents = ["delivery", "waitlist", "pick-up"]
intent_recognizer = IntentRecognizer(intents)
choice = intent_recognizer.classify("The caller placed an order an hour ago and wants to know if they can come collect it")

```

#### 4.2 DocumentQA

*Answer caller questions using provided documents (Plain Python String).*

```
# Constructor & Properties
guava.helpers.openai.DocumentQA(
  vector_store_name: str,
  document: str,
  client: Optional[openai.OpenAI] = None,
)

# Class Method Reference
# ask: Answer the question based on the `document` provided to the DocumentQA
def ask(
  question: str,
) -> str

# Example
from guava.helpers.openai import DocumentQA
from documents import some_text
document_qa = DocumentQA("my-restaurant-faq", some_text)
answer = document_qa.ask("Do you searve seafood")

```
