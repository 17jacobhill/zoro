# Zoro Learning System

Learn your coding patterns from Cline conversations, then automatically apply them to future tasks.

Simple CLI + `.clinerules/` files.

## Quick Start

```bash
# 1. Install
git clone https://github.com/jennygzma/zoro.git
cd zoro
pip install -e .

# 2. Initialize in YOUR project (not the zoro repo)
cd ~/my-project/
zoro init --user-name "Your Name"

# 3. Set up API key
cp .env.example .env
# Edit .env: add your API key (see below for options)
```

Done! Cline will now automatically use your learned rules.

## LLM Provider Configuration

Zoro supports multiple LLM providers. Choose the one that works best for your region:

### OpenAI (Global)
- Set `OPENAI_API_KEY` in your `.env` file
- Works globally but may be restricted in China

To configure your provider, edit the `.env` file and uncomment the appropriate settings.

## How It Works

1. **You work**: Build features with Cline as usual
2. **Export chat**: Save conversation to `.zoro/chat_history/`
3. **Process**: Run `zoro process` to extract patterns
4. **Auto-apply**: Before each user message, Cline:
   - Runs `zoro search "<task>"` 
   - Reads relevant rules from `.clinerules/zoro_context.md`
   - Applies your patterns automatically

## Commands

### `zoro init --user-name "Name"`
Initialize in your project. Creates:
- `.zoro/chat_history/` - Store exported chats here
- `.zoro/generated/` - Rules saved here (gitignored)
- `.clinerules/zoro_workflow.md` - Instructions for Cline

**Run from**: Your project root

### `zoro process `
Learn rules from Cline chat export.

Generates:
- Workflow rules (how you prefer to work)
- System rules (technical patterns)

### `zoro search <query> [options]`
Search your learned rules.

**Options**:
- `--type workflow|system` - Filter by type
- `--limit N` - Number of results (default: 3)
- `--output <file>` - Save to markdown file

**Examples**:
```bash
zoro search "error handling"
zoro search "React patterns" --type system --limit 5
```

## Using the Web UI (Optional)

To visualize and manage your rules/plans with the web interface:

```bash
# 1. Start API from YOUR project directory
cd ~/my-project/
zoro-api

# 2. In another terminal, start the frontend
cd ~/path/to/zoro/frontend/
npm run dev
```

The API will read/write data in `~/my-project/.zoro/`, and the web UI will connect to it.

**Note**: The web UI works with one project at a time. To switch projects, stop the API and restart it from the new project directory.

## Directory Structure

```
your-project/
├── .zoro/
│   ├── chat_history/          # Put exported Cline chats here
│   └── generated/             # Rules stored here (auto-created)
├── .clinerules/
│   ├── zoro_workflow.md       # Instructions for Cline
│   └── zoro_context.md        # Temp context (regenerated per task)
└── .env                        # Your OpenAI API key
```
