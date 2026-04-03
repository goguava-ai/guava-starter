# Product Search

**Direction:** Inbound

A customer calls to find a product in the catalog. The agent collects their category preference, use case, and budget, then queries MongoDB and reads back the top-rated matches.

## Query Strategy

Filters on `category` (case-insensitive regex), `price` (`$lte`), and optionally `in_stock: true`. Results are sorted by `rating` descending and capped at 5.

## Expected Document Shape

```json
{
  "name": "DataPulse Analytics",
  "category": "analytics",
  "price": 49.99,
  "rating": 4.7,
  "in_stock": true,
  "short_description": "Real-time API and event analytics with custom dashboards"
}
```

## Collection

`products`

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
