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

- Currently supported: `codex`, `cline`, `claude`
- Recommended default: `codex`
- The `claude` source reads the installed Claude Code client's own session
  files (`~/.claude/projects/<project>/*.jsonl`) and excludes sub-agent
  ("sidechain") turns from the transcript. If session discovery doesn't
  find anything, use the manual plan-import flow instead of relying on it.

You can set this in `.zoro/config.json`:

```json
{
  "chat_history_source": "claude"
}
```

## External Security Verifier (`verify-step` / `accept-risk`)

Zoro can gate a plan step behind an independently-executed external
verifier — the first one is [`security-audit`](https://github.com/17jacobhill/sec-audit)'s
`verify` command. Zoro launches it as a direct subprocess (never a
shell string), validates and hashes everything it reports, and only then
decides whether the step may complete. **Claude (or any coding agent)
can never satisfy this gate itself** — only `zoro verify-step` ever
launches the verifier, and only a named human can accept a
`PASS_WITH_RISK` result via `zoro accept-risk`.

Configure it in `.zoro/config.json`'s `verifiers` block (a full example, including `chat_history_source: "claude"`, is in [`config.example.json`](config.example.json)):

```json
{
  "verifiers": {
    "security-audit": {
      "kind": "command",
      "argv": [
        "node", "/absolute/path/to/sec-audit/dist/cli/index.js", "verify",
        "--repo", "{repo_root}",
        "--depth", "deep",
        "--invocation-id", "{invocation_id}",
        "--step-id", "{step_id}",
        "{plan_id_args}",
        "{rule_id_args}",
        "--expected-head", "{git_head}",
        "--result-file", "{result_file}"
      ],
      "schema": "zoro.security-audit.verifier-result/v1",
      "timeout_seconds": 1800,
      "pass_with_risk": "require_human",
      "require_complete_coverage": true,
      "gated_rule_categories": ["security"]
    }
  }
}
```

`{rule_id_args}` and `{plan_id_args}` are typed placeholders that expand
to zero or more complete argv elements (repeated `--rule-id <id>` pairs,
or nothing/`--plan-id <id>`) — never a joined or interpolated string.
A plan rule is gated behind a verifier if its `category` is listed in
that verifier's `gated_rule_categories`, or if the rule itself sets
`requires_verifier` to that verifier's id.

Usage:

```bash
zoro verify-step <step-id> --verifier security-audit
# on PASS_WITH_RISK, a named human must explicitly accept it:
zoro accept-risk <step-id> --invocation-id <id> --reason "<why this is acceptable>"
```

**Isolation warning**: `security-audit`'s Standard/Deep scan depths may
execute project-controlled build scripts or browser-extension code
against the repository being verified. Only point this at repositories
you already trust, exactly as you would running `security-audit` (or
any other build tooling) directly — this integration does not add
sandboxing of its own.

Evidence (the validated result envelope, a compact manifest, and
hashed artifact references) is stored under
`.zoro/visualization/<chat-id>/verifiers/<verifier-id>/<step-id>/<invocation-id>/`.
Since this repo's `.gitignore` excludes `.zoro/`, that evidence is local
to this machine by default — export it explicitly if you need
cross-machine or durable audit history; this integration does not
silently commit session state anywhere.

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
