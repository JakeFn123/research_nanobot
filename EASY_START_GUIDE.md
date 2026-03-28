# nanobot Easy Start Guide

This guide explains nanobot in plain language so you can quickly understand what it does and how to use it.

## 1) What is nanobot?

nanobot is a lightweight personal AI assistant framework.

In practice, it gives you:
- A command-line AI assistant (`nanobot agent`)
- A gateway service that connects the assistant to chat apps (`nanobot gateway`)
- Built-in tools (file read/write, shell, web search/fetch, scheduling, subagents)
- Persistent memory and workspace files so behavior can be customized over time

Think of it as: "a small, hackable agent runtime you can run locally and connect to Telegram/Discord/WhatsApp/etc."

## 2) What nanobot does under the hood

When you send a message:
1. Message enters nanobot (CLI or a chat channel)
2. Agent builds context from:
- system identity + runtime info
- workspace bootstrap files (`AGENTS.md`, `SOUL.md`, `USER.md`, `TOOLS.md`)
- memory files (`memory/MEMORY.md`, `memory/HISTORY.md`)
- available skills
3. LLM responds (and may call tools)
4. nanobot executes tool calls and loops until it has a final answer
5. Reply is sent back to CLI or the chat app

Main runtime parts:
- `nanobot/agent/loop.py`: core agent loop
- `nanobot/channels/manager.py`: channel lifecycle + outbound routing/retry
- `nanobot/cron/service.py`: scheduled jobs
- `nanobot/agent/memory.py`: memory consolidation

## 3) Important folders and files

Runtime defaults:
- Config: `~/.nanobot/config.json`
- Workspace: `~/.nanobot/workspace`

Workspace files you will use most:
- `SOUL.md`: assistant personality and values
- `USER.md`: your profile/preferences
- `TOOLS.md`: tool behavior notes
- `HEARTBEAT.md`: periodic tasks checklist
- `memory/MEMORY.md`: durable long-term facts
- `memory/HISTORY.md`: searchable history log
- `skills/`: your custom skills

## 4) Install from source (your current clone)

You already cloned the repo at:
- `/Users/jakefan/nanobot`

Recommended setup:

```bash
cd /Users/jakefan/nanobot
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

Verify:

```bash
nanobot --version
```

## 5) Fastest way to get working (2-3 minutes)

### Step A: Initialize files

```bash
nanobot onboard
```

Or interactive wizard:

```bash
nanobot onboard --wizard
```

### Step B: Edit config

Open `~/.nanobot/config.json` and set at least:
- one provider API key
- default model (+ provider recommended)

Example (OpenRouter):

```json
{
  "providers": {
    "openrouter": {
      "apiKey": "sk-or-v1-xxxx"
    }
  },
  "agents": {
    "defaults": {
      "provider": "openrouter",
      "model": "anthropic/claude-opus-4-5"
    }
  }
}
```

### Step C: Start chatting

```bash
nanobot agent
```

Single message mode:

```bash
nanobot agent -m "Help me summarize this project"
```

## 6) Two ways to run nanobot

### Mode 1: CLI assistant

Use this when you want terminal-based conversations.

```bash
nanobot agent
```

### Mode 2: Gateway (chat apps + periodic tasks)

Use this when you want Telegram/Discord/etc. integration and heartbeat scheduling.

```bash
nanobot gateway
```

## 7) Connect chat apps

nanobot supports multiple channels (Telegram, Discord, WhatsApp, Weixin, Feishu, DingTalk, Slack, Matrix, Email, QQ, Wecom, Mochat).

Typical flow:
1. Put channel config under `channels` in `~/.nanobot/config.json`
2. For QR/OAuth style channels, run:

```bash
nanobot channels login <channel>
```

3. Start gateway:

```bash
nanobot gateway
```

Check channel status:

```bash
nanobot channels status
```

## 8) Tools and safety model

By default, the agent can use tools such as:
- filesystem tools (read/write/edit/list)
- shell execution
- web search + web fetch
- scheduling and messaging tools

Safety control you should know:
- `tools.restrictToWorkspace`: when true, tool file access is limited to the workspace path

## 9) Scheduling and automation

There are two scheduling styles:

1. Heartbeat checklist (`HEARTBEAT.md`):
- Gateway checks this file every 30 minutes by default
- If tasks exist, agent executes and notifies your latest active chat channel

2. Cron jobs (tool-driven):
- Persisted in workspace at `cron/jobs.json`
- Supports one-time, interval, and cron-expression schedules

## 10) Customize behavior quickly

Most effective edits:
1. `SOUL.md`: set desired assistant behavior and tone
2. `USER.md`: your language, level, and work context
3. `AGENTS.md` (if present): high-priority operating rules
4. `skills/your-skill/SKILL.md`: add reusable workflows

Because these files are included in prompt context, changing them immediately changes assistant behavior.

## 11) Daily command cheat sheet

```bash
nanobot onboard
nanobot agent
nanobot agent -m "Hello"
nanobot gateway
nanobot status
nanobot channels status
nanobot channels login <channel>
nanobot provider login openai-codex
```

## 12) Troubleshooting

- `nanobot: command not found`
  - Activate virtualenv and reinstall `pip install -e .`
- No model response
  - Check `~/.nanobot/config.json` for API key + provider/model pair
- Channel not sending
  - Check `nanobot channels status`, credentials, and gateway logs
- Want isolated bot instances
  - Use `-c <config>` and `-w <workspace>` to run independent setups

## 13) Good first workflow to learn nanobot

1. `nanobot onboard --wizard`
2. Configure one provider key + model
3. Run `nanobot agent` and ask it to inspect a local folder
4. Edit `~/.nanobot/workspace/USER.md` to match your style
5. Enable one channel (Telegram is usually easiest)
6. Run `nanobot gateway`
7. Add one periodic task in `HEARTBEAT.md`

After this, you will understand the full framework lifecycle.
