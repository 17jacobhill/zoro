# Zoro

Zoro is a local-first workflow assistant for plan extraction, rule tracking, and coding-session visualization.

It includes:
- A Flask backend API
- A React + Vite frontend
- A `zoro` CLI for plan-step updates and rule evidence

## Requirements

- Python `3.10+`
- Node.js `20+`
- npm
- An OpenAI API key (`OPENAI_API_KEY`)

## Install Zoro (one-time)

Important:
- You must install Zoro as a Python package before using it in any target repo.
- This is what provides the `zoro` and `zoro-api` commands.

1. Clone this repository:

```bash
git clone https://github.com/<your-org-or-user>/<your-repo>.git
cd <your-repo>   # this is the zoro source repo
```

2. Create a Python env and install Zoro (required):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -e .
```

3. Confirm the CLI is installed in your active environment:

```bash
zoro --help
zoro-api --help
```

4. Install frontend dependencies (for the web UI):

```bash
npm install --prefix frontend
```

5. Configure environment variables:

```bash
cp .env.example .env
```

Then set at least:

```env
OPENAI_API_KEY=your_key_here
```

## Use Zoro In A Target Repo (recommended)

This is the key behavior:
- `zoro-api` must be run from the target repo root.
- `.zoro/` is created in whatever directory you run from.
- The Python environment where you installed Zoro must be active.

1. Open the repo you want Zoro to track:

```bash
cd /path/to/your-target-repo
```

2. Initialize Zoro in that target repo:

```bash
zoro init --user-name "Your Name"
```

3. Start the backend from that same target repo:

```bash
zoro-api
```

4. In a second terminal, run the frontend from the Zoro source repo:

```bash
cd /path/to/<your-zoro-source-repo>/frontend
npm run dev
```

5. Open:
- Backend API: `http://localhost:5010`
- Frontend UI: `http://127.0.0.1:5274`

## Develop Zoro Itself (this repo)

If you are developing this repository directly, you can run everything from here:

```bash
zoro-api
```

## Supported Chat Sources

- Currently supported: `codex`, `cline`
- Recommended default: `codex`
- Claude chat-history source support: coming soon

You can set this in `.zoro/config.json`:

```json
{
  "chat_history_source": "codex"
}
```

## Python Environment Notes

- You only need one active Python environment with `zoro` installed.
- That environment can live anywhere (for example in the Zoro source repo).
- When using Zoro in another target repo, activate the same environment, then `cd` into the target repo and run `zoro` / `zoro-api`.

`venv` vs Conda:
- Use `venv` unless you already rely on Conda for your workflow.
- Conda is optional; it is not required for Zoro.

## Rules Setup In `.zoro`

To seed rules manually in a target repo:

```bash
cd /path/to/your-target-repo
mkdir -p .zoro/rules/unstructured
```

Add markdown files to `.zoro/rules/unstructured`, for example:

```bash
cat > .zoro/rules/unstructured/team-rules.md <<'EOF'
# Backend Rules

- Keep route handlers thin.
- Keep business logic in service modules.
- Use typed schemas for API responses.
EOF
```

Then in the UI:
- Open **Rules Management**
- Click **Structure `file.md`** (or **Structure all pending files**)
- Optional: use **Structure repo AGENTS.md** to import repo-root `AGENTS.md` directly

Structured results are stored under `.zoro/rules/structured` (including `knowledge_base.json`).

## Troubleshooting

1. `OpenAI API key not found`
- Ensure `.env` exists and includes `OPENAI_API_KEY`.

2. Frontend can’t reach backend
- Confirm backend is on `5010` and frontend is on `5274`.
- Check browser console for CORS/API errors.

3. Port already in use
- Stop the process using `5010` or `5274`, then restart.

4. “No codex/cline chat history found”
- Zoro is local-history driven. Make sure your local chat history source exists and `.zoro/config.json` has the intended `chat_history_source`.
