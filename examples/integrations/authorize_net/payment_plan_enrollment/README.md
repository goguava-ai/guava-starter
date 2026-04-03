# Payment Plan Enrollment

**Direction:** Inbound

A patient calls to set up a monthly payment plan for an outstanding balance; the agent collects their information and card details, creates a customer profile, and schedules a recurring subscription.

## What it does

1. Greets the caller as Jordan from Harbor Health Services billing
2. Collects patient contact information (name, email, phone)
3. Collects the total outstanding balance and preferred monthly payment amount
4. Collects full credit or debit card details and billing address
5. Asks for the preferred start date for the first payment
6. Summarizes the plan (monthly amount, start date, estimated number of payments) and asks for confirmation
7. Calls `createCustomerProfileRequest` to store the patient's payment method securely
8. Calls `ARBCreateSubscriptionRequest` to schedule monthly recurring charges for the calculated number of billing cycles
9. Reads back the subscription confirmation ID and confirms the first payment date

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `AUTHORIZENET_API_LOGIN_ID` | Authorize.net API Login ID |
| `AUTHORIZENET_TRANSACTION_KEY` | Authorize.net Transaction Key |

## Usage

```bash
python __main__.py
```
