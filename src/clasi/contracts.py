"""Agent contract loading and validation.

Provides functions to load contract.yaml files, validate them against
the contract schema, and validate agent return values against their
declared return schemas.
"""

import json
import re
from pathlib import Path

import yaml

try:
    import jsonschema
except ImportError:  # pragma: no cover
    jsonschema = None  # type: ignore[assignment]


_CONTENT_ROOT = Path(__file__).parent.resolve()
_SCHEMA_PATH = _CONTENT_ROOT / "contract-schema.yaml"


def _load_schema() -> dict:
    """Load the contract JSON Schema from contract-schema.yaml."""
    return yaml.safe_load(_SCHEMA_PATH.read_text(encoding="utf-8"))


def _find_contract_path(agent_name: str) -> Path:
    """Find the contract.yaml for a named agent in the agent directory tree.

    Searches the agent directory under clasi/plugin/agents/
    for a directory matching the agent name containing a contract.yaml file.

    Args:
        agent_name: The agent name (e.g., "code-monkey", "sprint-planner").

    Returns:
        Path to the contract.yaml file.

    Raises:
        FileNotFoundError: If no contract.yaml is found for the agent.
    """
    agents_dir = _CONTENT_ROOT / "plugin" / "agents"
    if not agents_dir.exists():
        raise FileNotFoundError(
            f"Agents directory not found: {agents_dir}"
        )

    for contract_path in agents_dir.rglob("contract.yaml"):
        if contract_path.parent.name == agent_name:
            return contract_path

    # Build available list for error message
    available = sorted(
        p.parent.name for p in agents_dir.rglob("contract.yaml")
    )
    raise FileNotFoundError(
        f"No contract.yaml found for agent '{agent_name}'. "
        f"Available: {', '.join(available)}"
    )


def load_contract(agent_name: str) -> dict:
    """Load and validate a contract.yaml for a named agent.

    Finds the contract.yaml file in the agent directory tree, parses it,
    and validates it against the contract schema.

    Args:
        agent_name: The agent name (e.g., "code-monkey", "sprint-planner").

    Returns:
        The parsed contract as a dictionary.

    Raises:
        FileNotFoundError: If no contract.yaml is found for the agent.
        jsonschema.ValidationError: If the contract fails schema validation.
    """
    contract_path = _find_contract_path(agent_name)
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    validate_contract(contract)
    return contract


def validate_contract(contract: dict) -> None:
    """Validate a contract dict against the contract schema.

    Args:
        contract: A parsed contract.yaml dictionary.

    Raises:
        jsonschema.ValidationError: If the contract is invalid.
        RuntimeError: If jsonschema is not installed.
    """
    if jsonschema is None:
        raise RuntimeError(
            "jsonschema package is required for contract validation. "
            "Install it with: pip install jsonschema"
        )
    schema = _load_schema()
    jsonschema.validate(contract, schema)


def _extract_json_from_text(text: str) -> dict | None:
    """Extract the first JSON object from agent result text.

    Agents include their structured return as a JSON block in the
    result text. This function finds and parses it.

    Tries three strategies:
    1. Parse the entire text as JSON.
    2. Find a ```json fenced code block.
    3. Find the first { ... } block that parses as valid JSON.

    Returns:
        The parsed JSON object, or None if no valid JSON is found.
    """
    # Strategy 1: entire text is JSON
    text_stripped = text.strip()
    if text_stripped.startswith("{"):
        try:
            return json.loads(text_stripped)
        except json.JSONDecodeError:
            pass

    # Strategy 2: fenced code block
    match = re.search(r"```json\s*\n(.*?)\n\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Strategy 3: find first { ... } that parses
    brace_start = text.find("{")
    if brace_start >= 0:
        depth = 0
        for i in range(brace_start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[brace_start : i + 1])
                    except json.JSONDecodeError:
                        break

    return None


def validate_return(
    contract: dict,
    mode: str | None,
    result_text: str,
    work_dir: str,
) -> dict:
    """Validate an agent's return value against its contract.

    Extracts JSON from the agent's result text, validates it against
    the return schema declared in the contract, and checks that
    required output files exist.

    Args:
        contract: The agent's parsed contract dictionary.
        mode: The mode name (for multi-mode agents), or None for
            single-mode agents.
        result_text: The raw text returned by the agent.
        work_dir: The working directory for resolving output file paths.

    Returns:
        A dict with:
        - status: "valid", "invalid", or "error"
        - result_json: The extracted JSON (if any)
        - errors: List of error strings (if any)
        - missing_files: List of expected but missing output files
    """
    errors: list[str] = []
    missing_files: list[str] = []

    # Extract JSON from result text
    result_json = _extract_json_from_text(result_text)
    if result_json is None:
        return {
            "status": "error",
            "result_json": None,
            "errors": ["No valid JSON found in agent result text"],
            "missing_files": [],
        }

    # Determine the return schema to validate against
    returns = contract.get("returns", {})
    if mode is not None and isinstance(returns, dict) and "type" not in returns:
        # Multi-mode: returns is keyed by mode name
        return_schema = returns.get(mode)
        if return_schema is None:
            return {
                "status": "error",
                "result_json": result_json,
                "errors": [f"No return schema defined for mode '{mode}'"],
                "missing_files": [],
            }
    else:
        # Single-mode: returns is the schema directly
        return_schema = returns

    # Validate JSON against the return schema
    if jsonschema is not None and return_schema:
        try:
            jsonschema.validate(result_json, return_schema)
        except jsonschema.ValidationError as e:
            errors.append(f"Return validation failed: {e.message}")

    # Check output files exist
    outputs = contract.get("outputs", {})
    if mode is not None and isinstance(outputs, dict) and "required" not in outputs:
        # Multi-mode: outputs keyed by mode name
        mode_outputs = outputs.get(mode, {})
    else:
        # Single-mode
        mode_outputs = outputs

    required_outputs = mode_outputs.get("required", []) if isinstance(mode_outputs, dict) else []
    work_path = Path(work_dir)

    for output_spec in required_outputs:
        path_pattern = output_spec.get("path", "")
        # Skip template variables that can't be resolved here
        if "{" in path_pattern:
            continue
        if "*" in path_pattern or "?" in path_pattern:
            # Glob pattern
            matches = list(work_path.glob(path_pattern))
            min_count = output_spec.get("min_count", 1)
            if len(matches) < min_count:
                missing_files.append(
                    f"{path_pattern} (found {len(matches)}, need {min_count})"
                )
        else:
            # Exact file
            if not (work_path / path_pattern).exists():
                missing_files.append(path_pattern)

    status = "valid" if not errors and not missing_files else "invalid"
    return {
        "status": status,
        "result_json": result_json,
        "errors": errors,
        "missing_files": missing_files,
    }
