# Finanz butik - PoC: Bring Info from Basecamp to Code

This is a step-by-step guide to authenticate with the Basecamp API and retrieve data (cards, messages, etc.) using curl.

---

## Step 1 — Gather Required Information

Before making any API call, you need:

| Field | Value |
|---|---|
| Account ID | `5172885` |
| Project ID | `44382327` |
| Client ID | `c91ea9e7bc5363ac457e0520a8a662fff00d76e8` |
| Client Secret | *(regenerate at launchpad.37signals.com — never expose publicly)* |
| Access Token | *(obtained in Step 3)* |

---

## Step 2 — Get an Authorization Code (Browser)

Open this URL in your browser and authorize the app:

```
https://launchpad.37signals.com/authorization/new?type=web_server&client_id=c91ea9e7bc5363ac457e0520a8a662fff00d76e8&redirect_uri=http://localhost&response_type=code
```

After authorizing, the browser will redirect to something like:

```
http://localhost/?code=XXXXXXXX
```

Copy the `code` value from the URL — it expires in minutes, use it immediately.

---

## Step 3 — Exchange the Code for an Access Token (Git Bash Terminal)

Run this as a single line in Git Bash:

```bash
curl -X POST "https://launchpad.37signals.com/authorization/token" -d "type=web_server&client_id=c91ea9e7bc5363ac457e0520a8a662fff00d76e8&client_secret=YOUR_CLIENT_SECRET&redirect_uri=http://localhost&code=YOUR_CODE_HERE"
```

The response will be a JSON with an `access_token`:

```json
{
  "access_token": "BAhbB0ki...(long token)...",
  "token_type": "Bearer",
  "expires_in": 1209600,
  "refresh_token": "BAhbB0ki..."
}
```

Save the `access_token` — it is valid for 14 days.

---

## Step 4 — Make API Calls

Use the token in the `Authorization: Bearer` header.

> Important: Use `https://3.basecampapi.com` (not `https://3.basecamp.com`) for API calls.

### Get cards from a column (card table list)

```bash
curl -s -H "Authorization: Bearer YOUR_ACCESS_TOKEN" "https://3.basecampapi.com/5172885/buckets/44382327/card_tables/lists/COLUMN_ID/cards.json"
```

Note: Use `card_tables/lists/{id}` — NOT `card_tables/columns/{id}`.

### Get a message from a message board

```bash
curl -s -H "Authorization: Bearer YOUR_ACCESS_TOKEN" "https://3.basecampapi.com/5172885/buckets/44382327/messages/MESSAGE_ID.json"
```

### Verify your token and see your account info

```bash
curl -s -H "Authorization: Bearer YOUR_ACCESS_TOKEN" "https://launchpad.37signals.com/authorization.json"
```

---

## Known Column IDs — Development Kanban (Card Table: 9175270356)

| Column Name | Column ID | Cards URL |
|---|---|---|
| Figuring it out | `9175270358` | `.../card_tables/lists/9175270358/cards.json` |
| Not now | `9175270360` | `.../card_tables/lists/9175270360/cards.json` |
| To-Do | `9175270361` | `.../card_tables/lists/9175270361/cards.json` |
| Current Sprint | `9189476932` | `.../card_tables/lists/9189476932/cards.json` |
| In progress | `9175270366` | `.../card_tables/lists/9175270366/cards.json` |
| Ready for testing | `9189492964` | `.../card_tables/lists/9189492964/cards.json` |
| QA Testing | `9189481770` | `.../card_tables/lists/9189481770/cards.json` |
| Rechazado por QA | `9189481100` | `.../card_tables/lists/9189481100/cards.json` |
| QA Approved | `9189482585` | `.../card_tables/lists/9189482585/cards.json` |
| UAT Testing / Sandbox | `9189483373` | `.../card_tables/lists/9189483373/cards.json` |
| Redy to Deploy | `9189484543` | `.../card_tables/lists/9189484543/cards.json` |
| Production | `9175270369` | `.../card_tables/lists/9175270369/cards.json` |

---

## Common Mistakes to Avoid

- Do NOT use `https://3.basecamp.com` for API calls — use `https://3.basecampapi.com`
- Do NOT use `card_tables/columns/{id}` — use `card_tables/lists/{id}`
- Do NOT run multi-line curl with backticks (`) in Git Bash — always run as a single line
- Authorization codes expire within minutes — get a fresh one each time you need a new token
- Never commit or share your Client Secret publicly
