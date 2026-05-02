# tests/asr/

Two provider source directories used to demonstrate `clasr` and
exercise multi-tenant install behavior.

## What lives here

```
tests/asr/
  provider1/    — a "general engineering" provider: code-review,
                  security-audit skills; reviewer + scribe agents;
                  no-secrets and python-style rules; claude/
                  passthrough including settings.json and a
                  /changelog command; codex/notes.md; copilot/
                  .vscode/mcp.json. Exercises every clasr feature.

  provider2/    — a smaller "release-management" provider:
                  release-notes skill, release-manager agent,
                  claude/settings.json with non-overlapping
                  top-level keys (mcpServers — provider1 ships
                  model + permissions). Demonstrates clean
                  multi-tenant coexistence.

  project/      — the install target. Created by `just install`,
                  cleaned by `just clean-target`. Both providers
                  install into this single directory; their content
                  coexists via named marker blocks and per-provider
                  manifests.
```

`tests/asr/project/` is gitignored — it's a working directory the
demos write into and clean up. The two provider directories are
checked-in source content.

## Concepts

A **provider** ships an `asr/` directory with content (skills, agents,
rules, instructions). Examples: `clasi`, `curik`, `design-trainer`.

A **tool** is the LLM client (Claude Code, Codex, Copilot) that
consumes provider content from its conventional install paths
(`.claude/`, `.codex/`, `.github/`).

`clasr install` renders one provider's `asr/` into all the tool-
specific paths in a project, recording everything in a per-provider
manifest so uninstall is precise.

## Try it by hand

```sh
cd tests/asr
just demo                # multi-provider install + selective uninstall
just demo-single         # single-provider install/uninstall round-trip
just instructions        # print clasr's bundled how-to
just tree                # list everything clasr wrote
```
