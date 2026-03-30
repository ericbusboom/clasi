---
id: '001'
title: Create contract-schema.yaml and agent contracts
status: in-progress
use-cases:
- SUC-009
- SUC-010
depends-on: []
github-issue: ''
todo: sdk-orchestration-cluster/agent-contracts-as-process-description.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Create contract-schema.yaml and agent contracts

## Description

Create the contract infrastructure that defines the interface for every
dispatchable agent. This is the foundational design input for the entire
sprint -- all other tickets depend on the contract schema and per-agent
contract files.

Specifically:

1. **contract-schema.yaml** -- A JSON Schema file (in YAML format) that
   defines the structure of all agent contracts. This schema declares
   required fields such as `allowed_tools`, `mcp_servers`, `model`,
   `outputs`, `returns`, and `delegates_to`.

2. **Per-agent contract.yaml files** -- Create a `contract.yaml` in
   each agent directory for all 12 agents that participate in dispatch:
   team-lead, sprint-planner, sprint-executor, ad-hoc-executor,
   requirements-narrator, sprint-reviewer, todo-worker, architect,
   architecture-reviewer, code-monkey, code-reviewer, and technical-lead.
   The contract examples in
   `docs/clasi/todo/sdk-orchestration-cluster/contract-examples/` serve
   as starting points for these files.

3. **contracts.py module** -- A new Python module in the CLASI package
   with two key functions:
   - `load_contract(agent_name)` -- Loads and validates a contract.yaml
     against the schema, returning the parsed contract dict.
   - `validate_return(contract, result_json)` -- Validates a subagent's
     return JSON against the `returns` schema declared in the contract.

4. **get_agent_definition update** -- Extend the `get_agent_definition`
   MCP tool to return the contract content alongside the existing
   agent.md content, so subagents can read their own contract to format
   responses correctly (SUC-010).

5. **jsonschema dependency** -- Add `jsonschema` to pyproject.toml
   dependencies for schema validation.

## Acceptance Criteria

- [ ] `contract-schema.yaml` exists and validates all contract files
- [ ] `contract.yaml` exists for: team-lead, sprint-planner, sprint-executor, ad-hoc-executor, requirements-narrator, sprint-reviewer, todo-worker, architect, architecture-reviewer, code-monkey, code-reviewer, technical-lead
- [ ] `contracts.py` module exists with `load_contract()` and `validate_return()` functions
- [ ] `get_agent_definition` MCP tool returns contract content alongside agent.md
- [ ] `jsonschema` added to pyproject.toml dependencies
- [ ] Unit tests for contract schema validation (valid contract passes, invalid contract fails)
- [ ] Unit tests for `load_contract` and `validate_return`

## Testing

- **Existing tests to run**: `tests/test_process_tools.py` (get_agent_definition changes)
- **New tests to write**: `tests/test_contracts.py` -- tests for schema validation (valid passes, invalid fails), `load_contract` loading and validation, `validate_return` with conforming and non-conforming JSON
- **Verification command**: `uv run pytest`
