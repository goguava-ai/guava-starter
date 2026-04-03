# Product Availability

**Direction:** Inbound

A customer calls to check whether a specific item is in stock. The agent searches the `products` table by name or SKU and reads back availability, quantity, price, and store location.

## Expected Schema

```sql
CREATE TABLE products (
    id             INT PRIMARY KEY AUTO_INCREMENT,
    sku            VARCHAR(50) UNIQUE NOT NULL,
    name           VARCHAR(255) NOT NULL,
    category       VARCHAR(100),
    price          DECIMAL(10,2),
    stock_quantity INT DEFAULT 0,
    location       VARCHAR(100),   -- e.g. 'Aisle 3, Shelf B'
    updated_at     DATETIME DEFAULT NOW()
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
