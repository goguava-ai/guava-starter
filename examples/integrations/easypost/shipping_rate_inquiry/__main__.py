import logging
import os

import guava
import requests
from guava import logging_utils

EASYPOST_API_KEY = os.environ["EASYPOST_API_KEY"]
BASE_URL = "https://api.easypost.com/v2"


def create_shipment(
    from_street: str,
    from_city: str,
    from_state: str,
    from_zip: str,
    to_street: str,
    to_city: str,
    to_state: str,
    to_zip: str,
    weight_oz: float,
    length_in: float,
    width_in: float,
    height_in: float,
) -> dict | None:
    payload = {
        "shipment": {
            "from_address": {
                "street1": from_street,
                "city": from_city,
                "state": from_state,
                "zip": from_zip,
                "country": "US",
            },
            "to_address": {
                "street1": to_street,
                "city": to_city,
                "state": to_state,
                "zip": to_zip,
                "country": "US",
            },
            "parcel": {
                "length": length_in,
                "width": width_in,
                "height": height_in,
                "weight": weight_oz,
            },
        }
    }
    try:
        resp = requests.post(
            f"{BASE_URL}/shipments",
            auth=(EASYPOST_API_KEY, ""),
            json=payload,
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logging.error("EasyPost error creating shipment: %s", e)
        return None


def find_cheapest_and_fastest(rates: list) -> tuple[dict | None, dict | None]:
    if not rates:
        return None, None

    valid = [r for r in rates if r.get("rate") is not None]
    if not valid:
        return None, None

    cheapest = min(valid, key=lambda r: float(r["rate"]))

    fastest = None
    rates_with_days = [r for r in valid if r.get("delivery_days") is not None]
    if rates_with_days:
        fastest = min(rates_with_days, key=lambda r: int(r["delivery_days"]))

    return cheapest, fastest


agent = guava.Agent(
    name="Riley",
    organization="Summit Outfitters",
    purpose="to help customers get shipping rate quotes before sending a package",
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "shipping_rate_inquiry",
        objective=(
            "Collect the customer's origin and destination addresses along with package dimensions and weight, "
            "then look up real-time shipping rates and quote the cheapest and fastest options."
        ),
        checklist=[
            guava.Say(
                "Thanks for calling Summit Outfitters. This is Riley. I can help you get a shipping rate quote today."
            ),
            # From address
            guava.Field(
                key="from_street",
                field_type="text",
                description="Ask for the street address the package will be shipped FROM, including any apartment or suite number.",
                required=True,
            ),
            guava.Field(
                key="from_city",
                field_type="text",
                description="Ask for the city the package will be shipped from.",
                required=True,
            ),
            guava.Field(
                key="from_state",
                field_type="text",
                description="Ask for the state (two-letter abbreviation) the package will be shipped from.",
                required=True,
            ),
            guava.Field(
                key="from_zip",
                field_type="text",
                description="Ask for the ZIP code the package will be shipped from.",
                required=True,
            ),
            # To address
            guava.Field(
                key="to_street",
                field_type="text",
                description="Ask for the street address the package will be shipped TO.",
                required=True,
            ),
            guava.Field(
                key="to_city",
                field_type="text",
                description="Ask for the destination city.",
                required=True,
            ),
            guava.Field(
                key="to_state",
                field_type="text",
                description="Ask for the destination state (two-letter abbreviation).",
                required=True,
            ),
            guava.Field(
                key="to_zip",
                field_type="text",
                description="Ask for the destination ZIP code.",
                required=True,
            ),
            # Package details
            guava.Field(
                key="weight_oz",
                field_type="text",
                description="Ask for the package weight in ounces. If the customer gives pounds, let them know there are 16 ounces per pound.",
                required=True,
            ),
            guava.Field(
                key="length_in",
                field_type="text",
                description="Ask for the package length in inches.",
                required=True,
            ),
            guava.Field(
                key="width_in",
                field_type="text",
                description="Ask for the package width in inches.",
                required=True,
            ),
            guava.Field(
                key="height_in",
                field_type="text",
                description="Ask for the package height in inches.",
                required=True,
            ),
        ],
    )


def _parse_float(call: guava.Call, key: str, default: float = 1.0) -> float:
    try:
        return float(call.get_field(key))
    except (TypeError, ValueError):
        logging.warning("Could not parse field '%s' as float, using default %s", key, default)
        return default


@agent.on_task_complete("shipping_rate_inquiry")
def on_done(call: guava.Call) -> None:
    from_street = call.get_field("from_street")
    from_city = call.get_field("from_city")
    from_state = call.get_field("from_state")
    from_zip = call.get_field("from_zip")
    to_street = call.get_field("to_street")
    to_city = call.get_field("to_city")
    to_state = call.get_field("to_state")
    to_zip = call.get_field("to_zip")

    weight_oz = _parse_float(call, "weight_oz", default=16.0)
    length_in = _parse_float(call, "length_in", default=12.0)
    width_in = _parse_float(call, "width_in", default=12.0)
    height_in = _parse_float(call, "height_in", default=6.0)

    shipment = create_shipment(
        from_street=from_street,
        from_city=from_city,
        from_state=from_state,
        from_zip=from_zip,
        to_street=to_street,
        to_city=to_city,
        to_state=to_state,
        to_zip=to_zip,
        weight_oz=weight_oz,
        length_in=length_in,
        width_in=width_in,
        height_in=height_in,
    )

    if not shipment:
        call.hangup(
            final_instructions=(
                "Tell the customer you were unable to retrieve shipping rates at this time due to a technical issue. "
                "Apologize and suggest they try again later or visit the website for a quote. Be helpful and brief."
            )
        )
        return

    rates = shipment.get("rates", [])
    cheapest, fastest = find_cheapest_and_fastest(rates)

    if not cheapest and not fastest:
        call.hangup(
            final_instructions=(
                "Tell the customer that no shipping rates were returned for the addresses and package dimensions provided. "
                "This may be due to an unrecognized address. Suggest they double-check the addresses or visit the website. "
                "Be polite and helpful."
            )
        )
        return

    cheapest_summary = ""
    if cheapest:
        carrier = cheapest.get("carrier", "Unknown carrier")
        service = cheapest.get("service", "Standard")
        rate = cheapest.get("rate", "N/A")
        days = cheapest.get("delivery_days")
        days_str = f" ({days} business day{'s' if days != 1 else ''})" if days else ""
        cheapest_summary = f"Cheapest option: {carrier} {service} at ${rate}{days_str}."

    fastest_summary = ""
    if fastest and fastest.get("id") != (cheapest.get("id") if cheapest else None):
        carrier = fastest.get("carrier", "Unknown carrier")
        service = fastest.get("service", "Express")
        rate = fastest.get("rate", "N/A")
        days = fastest.get("delivery_days")
        days_str = f" ({days} business day{'s' if days != 1 else ''})" if days else ""
        fastest_summary = f"Fastest option: {carrier} {service} at ${rate}{days_str}."
    elif fastest and cheapest and fastest.get("id") == cheapest.get("id"):
        fastest_summary = "This is also the fastest available option."

    call.hangup(
        final_instructions=(
            f"Quote the following shipping rates to the customer. "
            f"{cheapest_summary} {fastest_summary} "
            "Let them know these rates are for a package shipped from "
            f"{from_city}, {from_state} to {to_city}, {to_state}, "
            f"weighing {weight_oz} ounces and measuring {length_in}x{width_in}x{height_in} inches. "
            "Let them know they can call back or visit the website to complete their purchase. "
            "Be friendly and clear."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
