---
status: in-progress
sprint: '001'
tickets:
- 001-001
---

# Agent Contracts as Process Description

## Problem

Agent definitions currently describe their role in prose: "What You
Receive" and "What You Return" sections written as natural language.
This is readable but not machine-actionable. The dispatch tools can't
validate inputs and outputs against the agent definition because
there's nothing structured to validate against.

Understanding the CLASI process currently requires reading all the
agent files, all the skill files, and mentally assembling the flow.
There's no single place where you can see: "the sprint-planner
receives these documents, produces these artifacts, and delegates to
these sub-agents under these conditions." The process is described
implicitly by the collection of agent files, not explicitly by any
one artifact.

## Desired Behavior

### 1. Each agent gets a contract.yaml alongside its agent.md

agent.md stays pure prose — role description, instructions, examples,
behavioral guidance. contract.yaml is the machine-readable contract:
inputs, outputs, return schema, delegation edges, allowed tools, MCP
access.

The contract serves three consumers:

**The dispatch tool (Python)** reads the contract to configure
`ClaudeAgentOptions` (allowed_tools, MCP servers, cwd), resolve
input documents, and validate the agent's return value against the
declared return schema.

**The agent itself** reads the contract (included in its prompt or
available via `get_agent_definition`) to know: what inputs it's
receiving, what files it must produce, what its return JSON must
look like, and who it can delegate to. The agent formats its final
response as JSON matching the return schema. This is not optional —
the dispatch tool validates it.

**Humans and process overview tools** read the contracts to understand
the process flow without assembling it from scattered prose.

### 2. Inputs are primarily documents

The dispatch prompt should be thin: "plan sprint 025 from these TODOs."
The substance comes from documents passed to the sub-agent. This makes
the contract inspectable — you can see exactly what the sub-agent had
to work with by looking at the dispatch log.

Each input is declared with:
- A name (for reference in the agent's prose instructions)
- A type: `file`, `file-list`, `text`, or `interactive`
- Whether it's required or optional
- A pattern or default for where it typically comes from

### 3. Optional documents for override/guidance

Some agents accept optional documents that augment their default
behavior:

- **Sprint planner**: `sprint-guidance` (external constraints on how
  to structure work), `prior-architecture` (current system state),
  `supplementary-context` (design sketches, meeting notes, anything
  the stakeholder wants considered).
- **Code monkey**: `implementation-notes` (stakeholder preferences
  or constraints for a specific ticket).

Optional documents are only passed when the caller provides them.
The agent's prose instructions describe how to use them when present.

### 4. contract.yaml IS the process description

Reading the contracts gives you the process:

- **team-lead** contract shows the delegation map: which agents it
  dispatches to and when.
- **sprint-planner** contract shows: receives TODOs and goals,
  produces sprint.md + usecases.md + architecture.md + tickets,
  delegates to architect, architecture-reviewer, technical-lead.
- **sprint-executor** contract shows: receives a sprint path,
  produces completed tickets, delegates to code-monkey.
- **code-monkey** contract shows: receives a ticket + plan, produces
  code + tests + updated frontmatter, delegates to nobody.

A tool can walk the hierarchy via `delegates_to` edges and reconstruct
the full process flow. Changes to the process are changes to
contract.yaml files. `get_se_overview` (or a new `get_process_overview`)
generates its output from the contracts instead of from static prose.

### 5. Contracts are validated by JSON Schema

A `contract-schema.yaml` file defines the schema for all contract.yaml
files. It's JSON Schema (draft 2020-12) written in YAML. Validation
in Python:

```python
import yaml, jsonschema
schema = yaml.safe_load(open("contract-schema.yaml"))
contract = yaml.safe_load(open("sprint-planner/contract.yaml"))
jsonschema.validate(contract, schema)
```

This means:
- The contract format is self-documenting (the schema describes every
  field).
- CI can validate all contracts against the schema.
- New agents get immediate feedback if their contract is malformed.
- The dispatch tools can trust the contract structure without defensive
  parsing.

## Schema Design

The schema defines these top-level fields:

| Field | Type | Purpose |
|-------|------|---------|
| `name` | string | Agent identifier, matches directory name |
| `tier` | 0/1/2 | Hierarchy level |
| `description` | string | One-paragraph role summary |
| `inputs` | object | `required` and `optional` arrays of input specs |
| `outputs` | object or keyed-by-mode | Files the agent must produce |
| `returns` | object | Schema for the JSON the agent returns to its caller |
| `delegates_to` | array | Delegation edges with `agent`, `mode`, `when` |
| `allowed_tools` | array | Tools for the SDK session |
| `mcp_servers` | array | MCP servers the agent connects to |
| `cwd` | string | Working directory (supports template variables) |

### Input spec fields

| Field | Required | Purpose |
|-------|----------|---------|
| `name` | yes | Reference name used in agent.md prose |
| `type` | yes | `file`, `file-list`, `text`, or `interactive` |
| `description` | yes | What this input is |
| `pattern` | no | Glob pattern for where it typically lives |
| `default` | no | Default path if caller doesn't provide one |

### Output spec fields

Outputs describe the files the agent must create or modify as side
effects. These are checked by the dispatch tool after the agent
returns (do the files exist? does the frontmatter match?).

| Field | Required | Purpose |
|-------|----------|---------|
| `path` | yes | Expected output file (globs allowed) |
| `min_count` | no | Minimum files matching a glob |
| `frontmatter` | no | Expected YAML frontmatter fields |
| `acceptance_criteria_checked` | no | All criteria must be `[x]` |

Outputs can be flat (single mode) or keyed by mode name (multi-mode
agents like sprint-planner with roadmap/detail).

### Return schema

The `returns` field describes the JSON object the agent must include
in its final response. This is what flows back through the dispatch
tool to the caller. The dispatch tool parses and validates it.

The agent reads this schema from its own contract and knows: "my last
message must contain a JSON block matching this shape." The dispatch
tool extracts the JSON from the agent's final message and validates
it before returning to the caller.

```yaml
returns:
  type: object
  required: [status, summary, files_created]
  properties:
    status:
      type: string
      enum: [success, partial, failed]
    summary:
      type: string
      description: Human-readable summary of what was accomplished
    files_created:
      type: array
      items:
        type: string
      description: Paths to files created or modified
    errors:
      type: array
      items:
        type: string
      description: Any issues encountered (present when status != success)
```

This is JSON Schema embedded in the contract YAML. Different agents
have different return shapes — sprint-planner returns a list of
created files and ticket IDs, code-monkey returns test results and
changed files, sprint-reviewer returns a pass/fail verdict with
findings.

The dispatch tool does two validations:
1. **File-level**: Check that declared output files exist with correct
   frontmatter (from the `outputs` section).
2. **Return-level**: Validate the agent's JSON response against the
   `returns` schema.

If either fails, the dispatch tool can retry the agent or return a
structured error to the caller.

### Delegation edge fields

| Field | Required | Purpose |
|-------|----------|---------|
| `agent` | yes | Target agent name |
| `mode` | no | Which mode if target has multiple |
| `when` | yes | Human-readable condition string |

The `when` field is informal — process documentation, not a formal
grammar. It describes when the delegation happens in plain English.
Not machine-evaluated; serves as the readable process description.

## Example Contracts

Full examples are in `contract-examples/`:
- `sprint-planner-contract.yaml` — two-mode agent (roadmap/detail)
- `code-monkey-contract.yaml` — leaf agent, no delegation
- `team-lead-contract.yaml` — tier 0 dispatcher, no Write/Edit
- `contract-schema.yaml` — JSON Schema that validates all of the above

## Proposed Changes

### 1. Create contract-schema.yaml

Add to the CLASI package as bundled content alongside agent definitions.
Installed by `clasi init` for reference. Used by dispatch tools at
runtime and by CI for validation.

### 2. Create contract.yaml for each agent

Add a `contract.yaml` file alongside each `agent.md` in the agent
directory tree:

```
agents/
├── main-controller/team-lead/
│   ├── agent.md
│   └── contract.yaml
├── domain-controllers/
│   ├── sprint-planner/
│   │   ├── agent.md
│   │   └── contract.yaml
│   ├── sprint-executor/
│   │   ├── agent.md
│   │   └── contract.yaml
│   └── ...
└── task-workers/
    ├── code-monkey/
    │   ├── agent.md
    │   └── contract.yaml
    └── ...
```

### 3. Update dispatch tools to read and use contracts

Each `dispatch_to_*` tool:
1. Loads the target agent's `contract.yaml`
2. Configures `ClaudeAgentOptions` from `allowed_tools`, `mcp_servers`,
   `cwd`
3. Resolves input documents (required and optional) from the contract
4. **Includes the contract in the agent's prompt** — the agent sees
   its own contract and knows what inputs it's receiving, what files
   it must produce, and what JSON shape to return
5. After `query()` returns, **validates the return JSON** against the
   `returns` schema
6. **Validates output files** against the `outputs` spec (files exist,
   frontmatter matches)
7. Returns structured result including validation status

The dispatch tool is the enforcement point. The agent reads the
contract and formats its response accordingly. The dispatch tool
validates both the response and the file-system side effects before
passing anything back to the caller.

### 4. Update get_agent_definition / get_agent_context

These MCP tools currently return agent.md content. Extend them to also
return the parsed contract.yaml so that callers (including agents
reading their own definition) can see the structured contract. This
matters for agents that delegate — the sprint-planner needs to read
the architect's contract to know what to pass it.

### 5. Add contract validation to CI

A test that loads every contract.yaml, validates it against the schema,
and checks that all `delegates_to` agent references point to agents
that actually exist.

### 6. Update get_se_overview to generate from contracts

Instead of returning static prose, walk the agent hierarchy via
`delegates_to` edges and generate a process description from the
contracts. This makes `get_se_overview` always current — it reflects
whatever the contracts say, not a manually maintained description.

## Open Questions

1. **Delegation conditions — stay informal?** The `when` field is
   currently a string. It could reference sprint phase values from the
   state DB ("when phase is executing"), but that adds coupling between
   the contract schema and the state machine. Keep informal for now;
   formalize later if the informal descriptions prove insufficient.

2. **Document passing mechanism**: The dispatch tool needs to pass
   the declared input documents. Options: (a) include file contents
   in the prompt, (b) pass file paths and let the sub-agent read them,
   (c) mix. Option (b) is simplest — the sub-agent has Read access
   and can decide what to read in detail. The contract declares what
   documents *should* be available, not how they're delivered.

3. **Process overview tool**: Extend `get_se_overview` to generate
   from contracts, or add a new `get_process_overview`? Extending
   the existing tool is cleaner — one tool, one source of truth. But
   `get_se_overview` currently returns a lot of non-contract content
   (MCP tool reference, skill list). Maybe it generates a section
   from contracts and keeps the rest.

4. **Versioning contract changes**: Changes to contract.yaml are
   process changes. Small tweaks (adjusting a description, adding an
   optional input) can be OOP. Structural changes (new delegation
   edges, new required inputs, new agents) should go through a sprint.
