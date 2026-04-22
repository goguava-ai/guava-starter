import guava
import os
import logging
import requests
from datetime import datetime, timedelta, timezone

logging.basicConfig(level=logging.INFO)

ES_URL = os.environ["ELASTICSEARCH_URL"].rstrip("/")
LOG_INDEX = os.environ.get("ELASTICSEARCH_LOG_INDEX", "logs-*")


def get_headers() -> dict:
    return {
        "Authorization": f"ApiKey {os.environ['ELASTICSEARCH_API_KEY']}",
        "Content-Type": "application/json",
    }


def search_logs(service: str, level: str = "", hours: int = 1) -> dict:
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")

    must: list[dict] = [
        {"range": {"@timestamp": {"gte": since}}},
    ]
    if service:
        must.append({"term": {"service.keyword": service}})
    if level:
        must.append({"term": {"level.keyword": level.upper()}})

    body = {
        "query": {"bool": {"must": must}},
        "size": 5,
        "sort": [{"@timestamp": {"order": "desc"}}],
        "_source": ["@timestamp", "level", "service", "message", "error.message"],
        "aggs": {
            "by_level": {
                "terms": {"field": "level.keyword", "size": 10}
            }
        },
    }

    resp = requests.post(
        f"{ES_URL}/{LOG_INDEX}/_search",
        headers=get_headers(),
        json=body,
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    hits = data.get("hits", {}).get("hits", [])
    total = data.get("hits", {}).get("total", {}).get("value", 0)
    buckets = data.get("aggregations", {}).get("by_level", {}).get("buckets", [])
    level_counts = {b["key"]: b["doc_count"] for b in buckets}

    return {
        "total": total,
        "level_counts": level_counts,
        "recent": [h["_source"] for h in hits],
    }


class LogInquiryController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Apex Store",
            agent_name="Morgan",
            agent_purpose=(
                "to help Apex Store engineers and on-call staff quickly query application logs by phone"
            ),
        )

        self.set_task(
            objective=(
                "An on-call engineer has called to check application logs. "
                "Collect the service name, log level filter, and time window, then summarize recent log activity."
            ),
            checklist=[
                guava.Say(
                    "Apex Store on-call line, this is Morgan. I can pull up log information for you."
                ),
                guava.Field(
                    key="service_name",
                    field_type="text",
                    description="Ask which service or application they'd like to check logs for.",
                    required=True,
                ),
                guava.Field(
                    key="log_level",
                    field_type="multiple_choice",
                    description="Ask what log level they want to filter by.",
                    choices=["ERROR", "WARN", "INFO", "DEBUG", "all"],
                    required=True,
                ),
                guava.Field(
                    key="time_window",
                    field_type="multiple_choice",
                    description="Ask how far back they'd like to look.",
                    choices=["15 minutes", "1 hour", "6 hours", "24 hours"],
                    required=True,
                ),
            ],
            on_complete=self.query_logs,
        )

        self.accept_call()

    def query_logs(self):
        service_name = self.get_field("service_name") or ""
        log_level = self.get_field("log_level") or "all"
        time_window = self.get_field("time_window") or "1 hour"

        hours_map = {
            "15 minutes": 0.25,
            "1 hour": 1,
            "6 hours": 6,
            "24 hours": 24,
        }
        hours = hours_map.get(time_window, 1)
        level_filter = "" if log_level == "all" else log_level

        logging.info(
            "Querying logs: service=%s, level=%s, hours=%s",
            service_name,
            level_filter,
            hours,
        )

        result = None
        try:
            result = search_logs(service=service_name, level=level_filter, hours=int(hours) or 1)
            logging.info("Log query complete: total=%s", result.get("total") if result else None)
        except Exception as e:
            logging.error("Failed to query logs: %s", e)

        if not result:
            self.hangup(
                final_instructions=(
                    "Apologize — we were unable to retrieve log data at this time. "
                    "Suggest the engineer check the Kibana dashboard directly. "
                    "Thank them for calling."
                )
            )
            return

        total = result["total"]
        level_counts = result["level_counts"]
        recent = result["recent"]

        level_summary = ", ".join(f"{k}: {v}" for k, v in level_counts.items()) if level_counts else "no data"
        recent_errors = [
            r for r in recent
            if r.get("level", "").upper() in ("ERROR", "FATAL")
        ]

        summary = (
            f"In the past {time_window}, service '{service_name}' has {total} log entries. "
            f"Log level breakdown: {level_summary}."
        )

        if recent_errors:
            latest_error = recent_errors[0]
            error_msg = latest_error.get("error.message") or latest_error.get("message", "")
            ts = latest_error.get("@timestamp", "")
            summary += f" Most recent error at {ts}: {error_msg[:200]}."

        self.hangup(
            final_instructions=(
                f"Read the following log summary to the engineer: {summary} "
                "Mention that they can drill down further in Kibana or call back for additional details. "
                "Thank them for calling."
            )
        )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=LogInquiryController,
    )
