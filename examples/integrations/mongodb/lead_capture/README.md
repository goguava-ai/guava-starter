# Lead Capture

**Direction:** Inbound

An inbound prospect calls Vantage. The agent collects their contact details, company size, use case, and timeline, then saves a rich lead document to MongoDB with `source: "inbound_voice"` and a UTC timestamp.

## Document Shape

```json
{
  "name": "Jane Smith",
  "email": "jane@acme.com",
  "company": "Acme Corp",
  "company_size": "51–200",
  "use_case": "We need better visibility into our API performance",
  "timeline": "1–3 months",
  "status": "new",
  "source": "inbound_voice",
  "created_at": "2026-03-26T14:22:00Z"
}
```

## Collection

`leads`

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `MONGODB_URI` | MongoDB Atlas connection string |
| `MONGODB_DATABASE` | Database name |

## Usage

```bash
python __main__.py
```
