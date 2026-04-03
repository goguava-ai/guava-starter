# Order Status

**Direction:** Inbound

A customer calls to check on an order. The agent collects the order number, queries the `orders` and `order_items` tables, and reads back the current status, line items, and estimated delivery date.

## Expected Schema

```sql
CREATE TABLE orders (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    order_number    VARCHAR(20) UNIQUE NOT NULL,
    customer_email  VARCHAR(255),
    status          VARCHAR(50),          -- e.g. 'processing', 'shipped', 'delivered'
    total_amount    DECIMAL(10,2),
    currency        VARCHAR(3) DEFAULT 'USD',
    estimated_delivery DATE,
    shipping_address TEXT,
    created_at      DATETIME DEFAULT NOW()
);

CREATE TABLE order_items (
    id           INT PRIMARY KEY AUTO_INCREMENT,
    order_id     INT NOT NULL REFERENCES orders(id),
    product_name VARCHAR(255),
    quantity     INT,
    unit_price   DECIMAL(10,2)
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
