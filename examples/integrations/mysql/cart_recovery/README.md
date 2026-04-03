# Cart Recovery

**Direction:** Outbound

Proactively calls customers who abandoned their shopping cart. The agent retrieves the cart and its items from the database, asks what stopped the customer from completing the purchase, and tries to recover the sale. The call outcome (`converted`, `interested`, `declined`, or `voicemail`) is written back to the `carts` table.

## Expected Schema

```sql
CREATE TABLE carts (
    id               INT PRIMARY KEY AUTO_INCREMENT,
    customer_name    VARCHAR(255),
    customer_email   VARCHAR(255),
    total_amount     DECIMAL(10,2),
    currency         VARCHAR(3) DEFAULT 'USD',
    recovery_outcome VARCHAR(50),   -- 'converted', 'interested', 'declined', 'voicemail'
    contacted_at     DATETIME,
    created_at       DATETIME DEFAULT NOW()
);

CREATE TABLE cart_items (
    id           INT PRIMARY KEY AUTO_INCREMENT,
    cart_id      INT NOT NULL REFERENCES carts(id),
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
python __main__.py +15551234567 --cart-id 42 --name "Jordan Smith"
```
