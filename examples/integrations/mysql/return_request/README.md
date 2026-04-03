# Return Request

**Direction:** Inbound

A customer calls to return an item. The agent verifies the order number against the `orders` table, collects the return details, and inserts a row into `return_requests` with a generated RMA number. A prepaid label is sent to the customer's email within 24 hours.

## Expected Schema

```sql
CREATE TABLE orders (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    order_number    VARCHAR(20) UNIQUE NOT NULL,
    customer_email  VARCHAR(255),
    status          VARCHAR(50),
    created_at      DATETIME DEFAULT NOW()
);

CREATE TABLE return_requests (
    id               INT PRIMARY KEY AUTO_INCREMENT,
    rma_number       VARCHAR(20) UNIQUE NOT NULL,
    order_number     VARCHAR(20) NOT NULL,
    customer_name    VARCHAR(255),
    customer_email   VARCHAR(255),
    item_description TEXT,
    return_reason    VARCHAR(100),
    item_condition   VARCHAR(100),
    status           VARCHAR(50) DEFAULT 'pending',
    created_at       DATETIME DEFAULT NOW()
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
