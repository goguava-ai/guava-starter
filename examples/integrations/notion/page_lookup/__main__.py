import guava
import os
import logging
import requests

logging.basicConfig(level=logging.INFO)

BASE_URL = "https://api.notion.com/v1"
DATABASE_ID = os.environ["NOTION_DATABASE_ID"]


def get_headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ['NOTION_TOKEN']}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


def search_pages(query: str) -> list[dict]:
    """Search the database for pages matching a query."""
    payload = {
        "filter": {
            "property": "title",
            "title": {"contains": query},
        },
        "page_size": 5,
    }
    resp = requests.post(
        f"{BASE_URL}/databases/{DATABASE_ID}/query",
        headers=get_headers(),
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("results", [])


def extract_title(page: dict) -> str:
    props = page.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "title":
            title_arr = prop.get("title", [])
            if title_arr:
                return title_arr[0].get("plain_text", "")
    return "Untitled"


def extract_property(page: dict, prop_name: str) -> str:
    prop = page.get("properties", {}).get(prop_name, {})
    ptype = prop.get("type", "")
    if ptype == "select":
        sel = prop.get("select")
        return sel.get("name", "") if sel else ""
    if ptype == "rich_text":
        texts = prop.get("rich_text", [])
        return texts[0].get("plain_text", "") if texts else ""
    if ptype == "date":
        date = prop.get("date")
        return date.get("start", "") if date else ""
    if ptype == "checkbox":
        return "Yes" if prop.get("checkbox") else "No"
    if ptype == "number":
        return str(prop.get("number", ""))
    return ""


class PageLookupController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Atlas Consulting",
            agent_name="Sam",
            agent_purpose="to help Atlas Consulting team members look up pages in Notion by phone",
        )

        self.set_task(
            objective=(
                "A team member has called to look up a page in Notion. "
                "Collect their search term, find the matching page, and read back the key details."
            ),
            checklist=[
                guava.Say(
                    "Atlas Consulting Notion lookup, this is Sam. What page are you looking for?"
                ),
                guava.Field(
                    key="search_query",
                    field_type="text",
                    description="Ask for the title or keyword of the Notion page they want to find.",
                    required=True,
                ),
            ],
            on_complete=self.lookup_page,
        )

        self.accept_call()

    def lookup_page(self):
        search_query = self.get_field("search_query") or ""

        logging.info("Searching Notion for: %s", search_query)

        pages = []
        try:
            pages = search_pages(search_query)
            logging.info("Found %d pages matching '%s'", len(pages), search_query)
        except Exception as e:
            logging.error("Failed to search Notion: %s", e)

        if not pages:
            self.hangup(
                final_instructions=(
                    f"Let the caller know no pages were found matching '{search_query}'. "
                    "They may want to try a different keyword. Thank them for calling."
                )
            )
            return

        page = pages[0]
        title = extract_title(page)
        notion_url = page.get("url", "")

        # Read back common properties
        status = extract_property(page, "Status")
        assignee = extract_property(page, "Assignee")
        due_date = extract_property(page, "Due Date")
        priority = extract_property(page, "Priority")

        details = f"Page: '{title}'."
        if status:
            details += f" Status: {status}."
        if assignee:
            details += f" Assignee: {assignee}."
        if due_date:
            details += f" Due: {due_date}."
        if priority:
            details += f" Priority: {priority}."
        if notion_url:
            details += f" URL: {notion_url}."

        if len(pages) > 1:
            details += f" ({len(pages) - 1} other matching pages found.)"

        self.hangup(
            final_instructions=(
                f"Read the following page details to the caller: {details} "
                "Thank them for calling Atlas Consulting."
            )
        )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=PageLookupController,
    )
