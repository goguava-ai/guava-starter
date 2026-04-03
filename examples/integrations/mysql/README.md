# MySQL Integration

Voice agents that query and write to a MySQL database — handling order lookups, appointment booking, and loyalty program inquiries without a web portal.

Uses [`PyMySQL`](https://pymysql.readthedocs.io/) for all database operations.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`order_status`](order_status/) | Inbound | Customer calls to check the status of their order by order number |
| [`appointment_booking`](appointment_booking/) | Inbound | Customer calls to schedule a service appointment |
| [`loyalty_points`](loyalty_points/) | Inbound | Customer calls to check their loyalty points balance and tier |
| [`product_availability`](product_availability/) | Inbound | Customer calls to check if a specific product or SKU is in stock |
| [`return_request`](return_request/) | Inbound | Customer calls to initiate a return; agent creates an RMA record |
| [`warranty_claim`](warranty_claim/) | Inbound | Customer calls to file a warranty claim on a defective product |
| [`cart_recovery`](cart_recovery/) | Outbound | Proactively call customers who abandoned their cart to recover the sale |

## Connection

All examples use a shared `get_connection()` helper that opens a new `pymysql` connection per call using environment variables. Connections are opened inside a `with` block to ensure they are always closed.

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `MYSQL_HOST` | MySQL server hostname |
| `MYSQL_PORT` | MySQL port (default: `3306`) |
| `MYSQL_USER` | MySQL username |
| `MYSQL_PASSWORD` | MySQL password |
| `MYSQL_DATABASE` | Database name |

## Installation

```bash
pip install PyMySQL
```
