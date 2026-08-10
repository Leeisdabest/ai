# Local Chat AI (Render)

Single-service chat website:

- Serves the chat UI at `/`
- Proxies AI requests at `/v1/chat/completions`
- API key stays on the server (Render env var)

## Deploy on Render (5 minutes)

1. Create a GitHub repo and upload **all files in this folder** (keep the structure).
2. Go to [https://dashboard.render.com](https://dashboard.render.com) → **New** → **Web Service**
3. Connect the GitHub repo
4. Settings:
   - **Runtime:** Python
   - **Build Command:** `true` (or leave blank if allowed)
   - **Start Command:** `python app.py`
5. **Environment** variables:

| Key | Example | Required |
|---|---|---|
| `API_KEY` | `sk-...` (OpenAI) or Groq/OpenRouter key | **Yes** |
| `UPSTREAM` | `https://api.openai.com/v1` | Yes |
| `DEFAULT_MODEL` | `gpt-4o-mini` | Yes |
| `SYSTEM_PROMPT` | your system prompt | Optional |

### Provider examples

**OpenAI**
```
UPSTREAM=https://api.openai.com/v1
DEFAULT_MODEL=gpt-4o-mini
API_KEY=sk-...
```

**Groq (fast + free tier)**
```
UPSTREAM=https://api.groq.com/openai/v1
DEFAULT_MODEL=llama-3.3-70b-versatile
API_KEY=gsk_...
```

**OpenRouter**
```
UPSTREAM=https://openrouter.ai/api/v1
DEFAULT_MODEL=openai/gpt-4o-mini
API_KEY=sk-or-...
```

6. Click **Create Web Service**
7. Open the URL Render gives you (e.g. `https://local-chat-ai.onrender.com`)

In the site Settings (usually auto-filled):

- Base URL: `https://YOUR-APP.onrender.com/v1`  (or just leave auto `/v1`)
- API key: `server`
- Model: same as `DEFAULT_MODEL`

## Repo structure

```
local-chat-ai/
├── app.py              # server
├── index.html          # chat UI (root fallback)
├── public/
│   └── index.html      # chat UI (preferred path)
├── requirements.txt
├── render.yaml         # optional Blueprint
├── Procfile
├── runtime.txt
├── .gitignore
└── README.md
```

**Important:** GitHub must include `public/index.html` **or** root `index.html`.
If you drag-and-drop files, open the `public` folder and upload `index.html` inside it too — empty folders / missed nested files cause:
`Missing UI file: .../public/index.html`

## Local test

```bash
export API_KEY=sk-...
export UPSTREAM=https://api.openai.com/v1
export DEFAULT_MODEL=gpt-4o-mini
python app.py
# open http://127.0.0.1:8787
```

## Notes

- Free Render services **spin down** after idle; first request can take ~30–60s.
- Never put your real API key in the HTML or commit it to GitHub.
- Health check: `GET /health`
