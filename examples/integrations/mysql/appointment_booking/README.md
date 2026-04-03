# Appointment Booking

**Direction:** Inbound

A customer calls to schedule a gear service or repair appointment. The agent collects their details and preferred date, generates a confirmation code, and inserts a row into the `appointments` table.

## Expected Schema

```sql
CREATE TABLE appointments (
    id                INT PRIMARY KEY AUTO_INCREMENT,
    confirmation_code VARCHAR(20) UNIQUE NOT NULL,
    customer_name     VARCHAR(255),
    customer_phone    VARCHAR(50),
    customer_email    VARCHAR(255),
    service_type      VARCHAR(100),
    preferred_date    VARCHAR(100),   -- stored as free text from the caller
    notes             TEXT,
    status            VARCHAR(50) DEFAULT 'pending',
    created_at        DATETIME DEFAULT NOW()
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
