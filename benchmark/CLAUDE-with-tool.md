# Copy this into the with-tool directory as CLAUDE.md

For Codex, name it `AGENTS.md` instead.

Everything below the line is what that session sees. Nothing else about the
tool is said to it.

It is deliberately short. It says the tool exists, what it is called, and that
`--help` explains it. It says nothing about how to model this problem, which
predicates to use, or how to order goals inside a rule — those are what the
comparison is meant to find out.

The recorded runs pointed at a wrapper script in a local checkout. With the
package installed, the command is simply `logic`, as below.

---

## Available tool: `logic`

A logic engine you can assert facts and rules into, and then query for
multi-step deduction. It is a command-line tool called `logic`.

Run `logic --help` for how it works.

The knowledge base is a file in the current directory, so it persists between
commands.
