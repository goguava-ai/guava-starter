# Warranty Claim

**Direction:** Inbound

A customer calls to file a warranty claim on a defective product. The agent collects their contact information, order number (optional), product details, and issue description, then inserts a record into `warranty_claims` with a generated claim number.

## Expected Schema

```sql
CREATE TABLE warranty_claims (
    id                  INT PRIMARY KEY AUTO_INCREMENT,
    claim_number        VARCHAR(20) UNIQUE NOT NULL,
    order_number        VARCHAR(20),
    customer_name       VARCHAR(255),
    customer_email      VARCHAR(255),
    customer_phone      VARCHAR(50),
    product_description TEXT,
    issue_description   TEXT,
    purchase_date       VARCHAR(100),   -- stored as free text from the caller
    status              VARCHAR(50) DEFAULT 'open',
    created_at          DATETIME DEFAULT NOW()
);
```

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `MYSQL_HOST` | MySQL server hostname |
| `MYSQL_USER` | MySQL username |
| `MYSQL_PASSWORD` | MySQL password |
| `MYSQL_DATABASE` | Database name |

## Usage

```bash
python __main__.py
```
