from notion_client import Client
from config import settings

_client = Client(auth=settings.notion_api_key)


def fetch_next_ticket() -> dict | None:
    """Return the lowest-wave, highest-priority 'Not started' ticket that isn't blocked."""
    response = _client.databases.query(
        database_id=settings.notion_database_id,
        filter={
            "property": "Status",
            "status": {"equals": "Not started"},
        },
        sorts=[
            {"property": "Execution Wave", "direction": "ascending"},
            {"property": "Priority", "direction": "ascending"},
        ],
    )

    for page in response.get("results", []):
        ticket = _parse_ticket(page)
        if "[AGENT BLOCKED]" not in (ticket.get("ticket_body") or ""):
            return ticket

    return None


def mark_in_progress(ticket_id: str) -> None:
    _client.pages.update(
        page_id=ticket_id,
        properties={"Status": {"status": {"name": "In progress"}}},
    )


def mark_done(ticket_id: str, pr_url: str) -> None:
    _client.pages.update(
        page_id=ticket_id,
        properties={
            "Status": {"status": {"name": "Done"}},
            "Description": {
                "rich_text": [
                    {"text": {"content": f"PR: {pr_url}"}},
                ]
            },
        },
    )


def mark_blocked(ticket_id: str, error: str, original_description: str) -> None:
    """No Blocked status in DB — write error to Description, reset to Not started."""
    error_block = f"[AGENT BLOCKED]\n{error}\n\n---\n\n{original_description}"
    _client.pages.update(
        page_id=ticket_id,
        properties={
            "Status": {"status": {"name": "Not started"}},
            "Description": {
                "rich_text": [
                    {"text": {"content": error_block[:2000]}},  # Notion limit
                ]
            },
        },
    )


def _parse_ticket(page: dict) -> dict:
    props = page["properties"]

    def text(prop) -> str:
        items = props.get(prop, {}).get("rich_text", [])
        return "".join(t["plain_text"] for t in items)

    def select(prop) -> str:
        s = props.get(prop, {}).get("select")
        return s["name"] if s else ""

    def multi_select(prop) -> list[str]:
        items = props.get(prop, {}).get("multi_select", [])
        return [i["name"] for i in items]

    def title(prop) -> str:
        items = props.get(prop, {}).get("title", [])
        return "".join(t["plain_text"] for t in items)

    def number(prop) -> int | None:
        return props.get(prop, {}).get("number")

    return {
        "ticket_id": page["id"],
        "ticket_title": title("Task Name"),
        "ticket_body": text("Description"),
        "ticket_priority": select("Priority"),
        "ticket_epic": select("Epic"),
        "ticket_roles": multi_select("Role"),
        "ticket_phase": select("Phase"),
        "ticket_depends_on": text("Depends On"),
        "ticket_wave": number("Execution Wave"),
    }
