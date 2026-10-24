# The `logic-cli` skill

[`logic-cli/`](logic-cli/) is a skill for Claude Code and OpenAI Codex. Both
follow the [Agent Skills](https://agentskills.io/specification) format, so the
same folder works in either.

Install Logic Layer first (see the main README), so that `logic` is on the
PATH of whatever environment the agent runs commands in.

## Installing it

Copy the whole `logic-cli` folder, not just `SKILL.md`:

| Agent | One project | Every project |
|---|---|---|
| Claude Code | `.claude/skills/logic-cli/` | `~/.claude/skills/logic-cli/` |
| OpenAI Codex | `.agents/skills/logic-cli/` | `~/.agents/skills/logic-cli/` |

The project paths are relative to the repository root. Both agents also find
skills in subfolders between the directory they start in and the root.

Claude Code can call it directly as `/logic-cli`, Codex as `$logic-cli`. Either
also loads it on its own when a task matches the description.

## What is in the folder

| File | Read by | Purpose |
|---|---|---|
| `SKILL.md` | both | The frontmatter says what the skill is for. The body is the CLI reference. |
| `agents/openai.yaml` | Codex only | Display name and short description in the Codex app. Claude Code ignores it. |

The folder name and the `name` field must match. Rename both or neither.

## What the skill says, and does not

The agent sees only the frontmatter `description` until it decides to load the
skill. That text says what the tool can do, not that it is worth using, and it
has to say something about when — a skill that never says when to load never
loads.

The body is a reference and nothing else: the commands, what the syntax
refuses, and what the answers mean. It does not say when the tool is worth
reaching for, because how much an agent uses it unprompted is the thing worth
finding out.

## Two things that may get in the way

**Sandboxing.** Some agents run commands in a container or with restricted
access, and may not see a `logic` installed outside it. Permission or
command-not-found errors usually mean this.

**The engine has to be reachable.** The tool looks for SWI-Prolog in
`LOGICLAYER_SWIPL` if set, then the standard Windows install folder, then the
PATH. A normal install is found without configuration. A copy kept anywhere
else needs `LOGICLAYER_SWIPL` pointed at it, in the environment the agent runs
in.

## The knowledge base

`logic.jsonl` is written wherever the command runs. Leave it in the project
root and commit it — it records what was established and why.

`logic history` prints it. `logic export --format html --out kb.html` draws it
as a single HTML file to open in any browser. Nothing more needs installing.
