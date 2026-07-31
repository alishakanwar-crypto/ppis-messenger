# Testing PPIS Messenger

End-to-end testing guide for the PPIS Messenger application (FastAPI backend + Vite React frontend).

## Prerequisites

### Start Services

```bash
# Backend (from ppis-messenger-backend/)
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8001

# Frontend (from ppis-messenger-frontend/)
npm run dev -- --port 5173
```

The backend auto-creates the SQLite database (`messenger.db`) and seeds admin users + groups on first start.

### Devin Secrets Needed

- **OPENAI_API_KEY** — Required for bot AI responses (optional; bot falls back to keyword matching without it)
- **WHATSAPP_APP_SECRET** — Only needed if testing HMAC webhook verification

## Authentication

The app uses OTP-based auth in demo mode. OTPs are shown directly in the UI and also returned in the API response.

```bash
# Request OTP
curl -s http://localhost:8001/api/auth/request-otp \
  -X POST -H "Content-Type: application/json" \
  -d '{"phone": "9971166562"}'
# Response includes otp_preview field

# Verify OTP (note: field is "code", not "otp")
curl -s http://localhost:8001/api/auth/verify-otp \
  -X POST -H "Content-Type: application/json" \
  -d '{"phone": "9971166562", "code": "<OTP>"}'
# Returns JWT token
```

**Admin phone numbers:** 9971166562, 9910034550, 9599488106, 8076455224

**Important:** The verify-otp endpoint uses field name `code`, not `otp`.

## Testing Admin Dashboard

### Seed WhatsApp Test Data

The admin dashboard shows channel breakdown only if WhatsApp messages exist. Seed test data directly:

```python
import sqlite3
conn = sqlite3.connect('ppis-messenger-backend/messenger.db')
cursor = conn.cursor()
cursor.execute("INSERT OR IGNORE INTO users (phone, name, role, grade, channel) VALUES ('913210000000', 'WhatsApp 3210', 'parent', '3A', 'whatsapp')")
wa_user_id = cursor.execute("SELECT id FROM users WHERE phone='913210000000'").fetchone()[0]
bot_id = cursor.execute("SELECT id FROM users WHERE phone='bot'").fetchone()[0]
cursor.execute("INSERT INTO messages (sender_id, recipient_id, content, message_type, is_bot, channel) VALUES (?, ?, 'Test message', 'text', 0, 'whatsapp')", (wa_user_id, bot_id))
conn.commit()
conn.close()
```

### Dashboard Verification

1. **Overview tab** (`/admin`): Look for "Messages by Channel" and "Parents by Channel" cards showing WhatsApp counts
2. **Chats tab**: Look for green "WA" badges next to WhatsApp conversations
3. The admin dashboard button is the gear icon in the top-right header bar

## Testing Bot Service

The bot uses a shared `bot_service.py` for both WhatsApp and in-app channels.

```bash
# Send message to bot (recipient_id=1 is always the bot)
curl -s http://localhost:8001/api/chat/send -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{"content": "Who is the class teacher for grade 3A?", "recipient_id": 1}'
```

Expected: Bot responds with teacher name "Reva Rajput" for Grade 3A.

## Testing Webhook Security

### GET Verification

```bash
# Correct token (default: ppis-messenger-verify-2026)
curl -s "http://localhost:8001/webhook/cloud?hub.mode=subscribe&hub.verify_token=ppis-messenger-verify-2026&hub.challenge=test_123"
# Should return: test_123

# Wrong token
curl -s -o /dev/null -w "%{http_code}" "http://localhost:8001/webhook/cloud?hub.mode=subscribe&hub.verify_token=wrong&hub.challenge=test_123"
# Should return: 403
```

### POST Dedup

Send the same `message_id` twice — second request should return `{"status":"duplicate"}`.

### HMAC Signature Verification

Restart backend with `WHATSAPP_APP_SECRET=<secret>` to enable HMAC verification. Then:

```bash
SECRET="test_secret_123"
PAYLOAD='{...}'
SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print $2}')

# With correct signature
curl -s -X POST http://localhost:8001/webhook/cloud \
  -H "Content-Type: application/json" \
  -H "X-Hub-Signature-256: sha256=$SIGNATURE" \
  -d "$PAYLOAD"
```

Without `WHATSAPP_APP_SECRET` set, HMAC verification is skipped (useful for dev/testing).

## Common Pitfalls

- The database file is `messenger.db` (not `ppis_messenger.db`) in the backend directory
- The frontend login page may get stuck on "Sending..." if the backend is slow or unrestarted — reload the page
- API routes are under `/api/` prefix (e.g., `/api/auth/request-otp`), except the webhook which is at `/webhook/cloud`
- The verify-otp field is `code` not `otp` — this is a common mistake
- Admin dashboard is accessible via the gear icon button in the header (title="Admin Dashboard")
- Bot user always has phone='bot' and id=1 in the database
