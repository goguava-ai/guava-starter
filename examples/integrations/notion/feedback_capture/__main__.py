import guava
import os
import logging
import requests
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)

BASE_URL = "https://api.notion.com/v1"
DATABASE_ID = os.environ["NOTION_DATABASE_ID"]


def get_headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ['NOTION_TOKEN']}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


def create_feedback_page(
    submitter: str,
    category: str,
    rating: str,
    feedback: str,
    follow_up_needed: bool,
) -> dict | None:
    properties: dict = {
        "Name": {
            "title": [{"text": {"content": f"Feedback from {submitter} — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"}}]
        },
        "Status": {"select": {"name": "New"}},
    }

    if submitter:
        properties["Submitter"] = {"rich_text": [{"text": {"content": submitter}}]}
    if category:
        properties["Category"] = {"select": {"name": category}}
    if rating:
        try:
            properties["Rating"] = {"number": int(rating)}
        except ValueError:
            pass
    if follow_up_needed is not None:
        properties["Follow-Up Needed"] = {"checkbox": follow_up_needed}

    properties["Date"] = {"date": {"start": datetime.now(timezone.utc).strftime("%Y-%m-%d")}}

    children = []
    if feedback:
        children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": feedback}}]
            },
        })

    payload: dict = {
        "parent": {"database_id": DATABASE_ID},
        "properties": properties,
    }
    if children:
        payload["children"] = children

    resp = requests.post(f"{BASE_URL}/pages", headers=get_headers(), json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()


class FeedbackCaptureController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Atlas Consulting",
            agent_name="Sam",
            agent_purpose=(
                "to collect feedback from Atlas Consulting clients and team members and log it to Notion"
            ),
        )

        self.set_task(
            objective=(
                "A caller wants to leave feedback. Collect their name, category of feedback, "
                "a rating, and their detailed comments, then log it to Notion."
            ),
            checklist=[
                guava.Say(
                    "Atlas Consulting feedback line, this is Sam. "
                    "I'd love to hear your thoughts — please go ahead."
                ),
                guava.Field(
                    key="submitter_name",
                    field_type="text",
                    description="Ask for their name.",
                    required=True,
                ),
                guava.Field(
                    key="category",
                    field_type="multiple_choice",
                    description="Ask what area their feedback relates to.",
                    choices=["Service Quality", "Communication", "Pricing", "Team", "Product", "Other"],
                    required=True,
                ),
                guava.Field(
                    key="rating",
                    field_type="multiple_choice",
                    description="Ask them to rate their experience on a scale of 1 to 5.",
                    choices=["1", "2", "3", "4", "5"],
                    required=True,
                ),
                guava.Field(
                    key="feedback_text",
                    field_type="text",
                    description="Ask them to share their detailed feedback or comments.",
                    required=True,
                ),
                guava.Field(
                    key="follow_up",
                    field_type="multiple_choice",
                    description="Ask if they'd like someone from the team to follow up with them.",
                    choices=["yes", "no"],
                    required=True,
                ),
            ],
            on_complete=self.save_feedback,
        )

        self.accept_call()

    def save_feedback(self):
        submitter_name = self.get_field("submitter_name") or ""
        category = self.get_field("category") or "Other"
        rating = self.get_field("rating") or ""
        feedback_text = self.get_field("feedback_text") or ""
        follow_up = self.get_field("follow_up") or "no"
        follow_up_needed = follow_up == "yes"

        logging.info(
            "Saving feedback from %s: category=%s, rating=%s, follow_up=%s",
            submitter_name,
            category,
            rating,
            follow_up_needed,
        )

        created = None
        try:
            created = create_feedback_page(
                submitter=submitter_name,
                category=category,
                rating=rating,
                feedback=feedback_text,
                follow_up_needed=follow_up_needed,
            )
            logging.info("Feedback page created: %s", created.get("id") if created else None)
        except Exception as e:
            logging.error("Failed to create feedback page: %s", e)

        if created:
            self.hangup(
                final_instructions=(
                    f"Thank {submitter_name or 'them'} sincerely for taking the time to share their feedback. "
                    + (
                        "Let them know a member of the Atlas Consulting team will follow up soon. "
                        if follow_up_needed
                        else "Let them know their feedback has been recorded and will be reviewed by the team. "
                    )
                    + "Wish them a great day."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Thank {submitter_name or 'them'} for their feedback. "
                    "Apologize that we had a technical issue saving it. "
                    "Let them know our team will still follow up if they requested it. "
                    "Wish them a great day."
                )
            )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=FeedbackCaptureController,
    )
