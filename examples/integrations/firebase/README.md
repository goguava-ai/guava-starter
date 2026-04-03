# Firebase / Firestore Integration

Voice agents that integrate with [Cloud Firestore](https://firebase.google.com/docs/firestore) to look up customer records, write call outcomes, manage appointments, and check order status — using Firestore as a real-time, serverless backend.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`customer_profile_lookup`](customer_profile_lookup/) | Inbound | Look up a caller's profile in Firestore and personalize the interaction |
| [`appointment_booking`](appointment_booking/) | Inbound | Customer calls to book an appointment; it is written to Firestore |
| [`feedback_collection`](feedback_collection/) | Outbound | Agent calls customers for post-service feedback and writes results to Firestore |
| [`order_status_check`](order_status_check/) | Inbound | Customer calls to check order status stored in Firestore |

## Authentication

All examples use the `firebase-admin` SDK with a service account:

```python
import firebase_admin
from firebase_admin import credentials, firestore

cred = credentials.Certificate(os.environ["GOOGLE_APPLICATION_CREDENTIALS"])
firebase_admin.initialize_app(cred)
db = firestore.client()
```

Set `GOOGLE_APPLICATION_CREDENTIALS` to the path of your service account JSON file downloaded from the Firebase console: **Project Settings** → **Service Accounts** → **Generate new private key**.

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to the Firebase service account JSON file |

## Firestore Reference

- [Get started with Firestore](https://firebase.google.com/docs/firestore/quickstart)
- [Add and manage data](https://firebase.google.com/docs/firestore/manage-data/add-data)
- [Query data](https://firebase.google.com/docs/firestore/query-data/queries)
