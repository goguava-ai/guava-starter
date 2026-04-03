# MongoDB Atlas Integration

Voice agents that read from and write to a MongoDB Atlas cluster — capturing leads, updating customer preferences, and searching a product catalog.

Uses [`pymongo`](https://pymongo.readthedocs.io/) for all database operations.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`lead_capture`](lead_capture/) | Inbound | Inbound prospect call saves a rich lead document to MongoDB |
| [`preference_update`](preference_update/) | Inbound | Customer updates their notification and communication preferences |
| [`product_search`](product_search/) | Inbound | Customer calls to find a product; agent queries the catalog and makes a recommendation |

## Connection

All examples create a module-level `MongoClient` from `MONGODB_URI` and access a named database. The client is thread-safe and reused across calls.

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `MONGODB_URI` | MongoDB Atlas connection string (`mongodb+srv://...`) |
| `MONGODB_DATABASE` | Database name |

## Installation

```bash
pip install pymongo
```
