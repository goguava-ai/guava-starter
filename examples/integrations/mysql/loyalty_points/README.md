# Loyalty Points

**Direction:** Inbound

A loyalty member calls to check their points balance and tier status. The agent looks them up by email or phone number and reads back their points, current tier, perks, and how many points they need to reach the next tier.

## Expected Schema

```sql
CREATE TABLE customers (
    id             INT PRIMARY KEY AUTO_INCREMENT,
    name           VARCHAR(255),
    email          VARCHAR(255) UNIQUE,
    phone          VARCHAR(50),
    loyalty_points INT DEFAULT 0,
    loyalty_tier   ENUM('bronze','silver','gold','platinum') DEFAULT 'bronze',
    created_at     DATETIME DEFAULT NOW()
);
```

## Tier Thresholds

| Tier | Points required | Perk |
|---|---|---|
| Bronze | 0 | 5% off all purchases |
| Silver | 500 | 10% off + free shipping |
| Gold | 2,000 | 15% off + priority service |
| Platinum | 5,000 | 20% off + free gear checks |

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
