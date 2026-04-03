# Payment Status Inquiry

**Direction:** Inbound

A customer calls Meridian Commerce to check the status of a payment, refund, or payment link. The voice agent collects their contact details and inquiry type, then either performs a live lookup against the Adyen Checkout API (for payment links) or provides accurate guidance on Adyen's webhook-driven status model (for direct payments and refunds).

## What it does

1. Greets the caller and explains it can help with payment, refund, or payment link status checks.
2. Collects the customer's email address and their payment or order reference number.
3. Asks what type of status inquiry they have (payment, refund, or payment link).
4. **Payment link status:** looks up the link via `GET /paymentLinks/{linkId}` and reads back the current status (paid, active, or expired) along with the amount. If the reference provided is not a link ID (does not start with "PL"), prompts the customer for the specific link ID.
5. **Refund status:** explains that refund updates are delivered by email and provides timeline guidance (3–5 business days). Offers billing team follow-up for overdue refunds.
6. **Payment status:** guides the customer to check for a confirmation email and offers to look up by payment link ID if applicable. Offers billing team follow-up if unresolved.

## Notes on Adyen's Architecture

Adyen is fundamentally a webhook-driven platform. Payment authorization results (`AUTHORISATION`) and refund completions (`REFUND`, `REFUND_FAILED`) are delivered as server-to-server notifications rather than being queryable via a polling REST endpoint. This example reflects that reality:

- Payment link status is the one inquiry type that supports a synchronous REST lookup (`GET /paymentLinks/{id}`).
- For direct payments and refunds, the agent provides accurate guidance and routes to the billing team for follow-up rather than presenting fabricated or stale data.

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ADYEN_API_KEY` | Adyen API key from the Customer Area |
| `ADYEN_MERCHANT_ACCOUNT` | Your Adyen merchant account name |
| `ADYEN_CHECKOUT_URL` | Checkout API base URL (default: `https://checkout-test.adyen.com/v71`) |

## Usage

```bash
python __main__.py
```
