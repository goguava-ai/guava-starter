# Monday.com Integration

Voice agents that integrate with the [Monday.com GraphQL API](https://developer.monday.com/api-reference) to check item status, create new work items, post updates, and handle task assignments — for teams managing projects and workflows on monday.com.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`item_status_check`](item_status_check/) | Inbound | Caller asks about the status of a task or project item |
| [`item_creation`](item_creation/) | Inbound | Caller creates a new item on a monday.com board |
| [`project_update`](project_update/) | Inbound | Post an update on an item and optionally change its status column |
| [`task_assignment`](task_assignment/) | Inbound | Caller assigns a task item to a team member and sets a due date |

## Authentication

All examples use an API token in the `Authorization` header:

```python
headers = {
    "Authorization": os.environ["MONDAY_API_TOKEN"],
    "Content-Type": "application/json",
}
```

Generate your API token at **Profile → Developers → My Access Tokens** in the monday.com UI.

## API Endpoint

Monday.com uses a GraphQL API:

```
https://api.monday.com/v2
```

All requests are `POST` with a JSON body containing a `query` (or `mutation`) string.

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `MONDAY_API_TOKEN` | Monday.com API token |
| `MONDAY_BOARD_ID` | Target board ID |

## Usage

```bash
python -m examples.integrations.monday.item_status_check
python -m examples.integrations.monday.item_creation
python -m examples.integrations.monday.project_update
python -m examples.integrations.monday.task_assignment
```

## Monday.com API Reference

- [Items](https://developer.monday.com/api-reference/reference/items)
- [Boards](https://developer.monday.com/api-reference/reference/boards)
- [Updates](https://developer.monday.com/api-reference/reference/updates)
- [Column Values](https://developer.monday.com/api-reference/reference/column-values)
