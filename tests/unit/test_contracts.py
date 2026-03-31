"""Tests for clasi.contracts module."""

import json
from pathlib import Path

import pytest
import yaml

from clasi.contracts import (
    _extract_json_from_text,
    _find_contract_path,
    _load_schema,
    load_contract,
    validate_contract,
    validate_return,
)
from clasi.mcp_server import content_path


class TestContractSchema:
    """Tests for the contract-schema.yaml file itself."""

    def test_schema_file_exists(self):
        schema_path = content_path("contract-schema.yaml")
        assert schema_path.exists(), "contract-schema.yaml must exist"

    def test_schema_is_valid_yaml(self):
        schema = _load_schema()
        assert isinstance(schema, dict)

    def test_schema_is_valid_json_schema(self):
        import jsonschema

        schema = _load_schema()
        # A valid JSON Schema should at least have $schema and type
        assert "$schema" in schema
        assert schema["type"] == "object"
        # Validate the schema itself is well-formed by checking it
        # against the JSON Schema meta-schema
        jsonschema.Draft202012Validator.check_schema(schema)

    def test_schema_has_required_fields(self):
        schema = _load_schema()
        required = schema.get("required", [])
        expected = [
            "name", "tier", "description", "inputs",
            "outputs", "returns", "delegates_to", "allowed_tools",
        ]
        for field in expected:
            assert field in required, f"'{field}' should be required"

    def test_schema_has_model_field(self):
        schema = _load_schema()
        props = schema.get("properties", {})
        assert "model" in props
        model_prop = props["model"]
        assert model_prop["type"] == "string"
        assert set(model_prop["enum"]) == {"opus", "sonnet", "haiku"}


# All expected agent names
ALL_AGENTS = [
    "team-lead",
    "sprint-planner",
    "sprint-executor",
    "ad-hoc-executor",
    "sprint-reviewer",
    "todo-worker",
    "project-manager",
    "project-architect",
    "architect",
    "architecture-reviewer",
    "code-monkey",
    "code-reviewer",
    "technical-lead",
]


class TestAllContractsValid:
    """Tests that every contract.yaml validates against the schema."""

    @pytest.mark.parametrize("agent_name", ALL_AGENTS)
    def test_contract_exists(self, agent_name):
        path = _find_contract_path(agent_name)
        assert path.exists(), f"contract.yaml must exist for {agent_name}"

    @pytest.mark.parametrize("agent_name", ALL_AGENTS)
    def test_contract_validates(self, agent_name):
        contract = load_contract(agent_name)
        assert contract["name"] == agent_name

    @pytest.mark.parametrize("agent_name", ALL_AGENTS)
    def test_contract_has_consistent_name(self, agent_name):
        contract = load_contract(agent_name)
        assert contract["name"] == agent_name, (
            f"Contract name '{contract['name']}' doesn't match "
            f"directory name '{agent_name}'"
        )


class TestLoadContract:
    """Tests for load_contract function."""

    def test_loads_known_agent(self):
        contract = load_contract("code-monkey")
        assert contract["name"] == "code-monkey"
        assert contract["tier"] == 2
        assert isinstance(contract["allowed_tools"], list)

    def test_loads_team_lead(self):
        contract = load_contract("team-lead")
        assert contract["tier"] == 0
        assert len(contract["delegates_to"]) > 0

    def test_not_found_raises(self):
        with pytest.raises(FileNotFoundError, match="nonexistent"):
            load_contract("nonexistent-agent")

    def test_model_field_present_when_set(self):
        contract = load_contract("sprint-planner")
        assert contract.get("model") == "opus"

    def test_model_field_absent_for_team_lead(self):
        contract = load_contract("team-lead")
        assert "model" not in contract


class TestValidateContract:
    """Tests for validate_contract function."""

    def test_valid_contract_passes(self):
        contract = {
            "name": "test-agent",
            "tier": 2,
            "description": "A test agent",
            "inputs": {},
            "outputs": {"required": []},
            "returns": {"type": "object", "required": ["status"], "properties": {"status": {"type": "string"}}},
            "delegates_to": [],
            "allowed_tools": ["Read"],
        }
        # Should not raise
        validate_contract(contract)

    def test_missing_required_field_fails(self):
        import jsonschema as js

        contract = {
            "name": "test-agent",
            "tier": 2,
            # Missing description, inputs, outputs, returns, delegates_to, allowed_tools
        }
        with pytest.raises(js.ValidationError):
            validate_contract(contract)

    def test_invalid_tier_fails(self):
        import jsonschema as js

        contract = {
            "name": "test-agent",
            "tier": 5,  # Invalid
            "description": "A test agent",
            "inputs": {},
            "outputs": {"required": []},
            "returns": {"type": "object"},
            "delegates_to": [],
            "allowed_tools": [],
        }
        with pytest.raises(js.ValidationError):
            validate_contract(contract)

    def test_invalid_model_fails(self):
        import jsonschema as js

        contract = {
            "name": "test-agent",
            "tier": 2,
            "model": "gpt-4",  # Invalid
            "description": "A test agent",
            "inputs": {},
            "outputs": {"required": []},
            "returns": {"type": "object"},
            "delegates_to": [],
            "allowed_tools": [],
        }
        with pytest.raises(js.ValidationError):
            validate_contract(contract)


class TestExtractJson:
    """Tests for JSON extraction from result text."""

    def test_pure_json(self):
        result = _extract_json_from_text('{"status": "success"}')
        assert result == {"status": "success"}

    def test_fenced_code_block(self):
        text = 'Here is the result:\n```json\n{"status": "success"}\n```\n'
        result = _extract_json_from_text(text)
        assert result == {"status": "success"}

    def test_embedded_json(self):
        text = 'Done! Result: {"status": "success", "count": 3} end.'
        result = _extract_json_from_text(text)
        assert result == {"status": "success", "count": 3}

    def test_no_json(self):
        result = _extract_json_from_text("No JSON here at all.")
        assert result is None

    def test_nested_json(self):
        text = '{"outer": {"inner": "value"}, "list": [1, 2]}'
        result = _extract_json_from_text(text)
        assert result == {"outer": {"inner": "value"}, "list": [1, 2]}


class TestValidateReturn:
    """Tests for validate_return function."""

    def test_valid_return_single_mode(self):
        contract = {
            "returns": {
                "type": "object",
                "required": ["status"],
                "properties": {
                    "status": {"type": "string", "enum": ["success", "failed"]},
                },
            },
            "outputs": {"required": []},
        }
        result = validate_return(
            contract, None, '{"status": "success"}', "/tmp"
        )
        assert result["status"] == "valid"
        assert result["result_json"] == {"status": "success"}
        assert result["errors"] == []

    def test_invalid_return_value(self):
        contract = {
            "returns": {
                "type": "object",
                "required": ["status"],
                "properties": {
                    "status": {"type": "string", "enum": ["success", "failed"]},
                },
            },
            "outputs": {"required": []},
        }
        result = validate_return(
            contract, None, '{"status": "maybe"}', "/tmp"
        )
        assert result["status"] == "invalid"
        assert len(result["errors"]) > 0

    def test_missing_json_returns_error(self):
        contract = {
            "returns": {"type": "object"},
            "outputs": {"required": []},
        }
        result = validate_return(
            contract, None, "No JSON here", "/tmp"
        )
        assert result["status"] == "error"
        assert "No valid JSON" in result["errors"][0]

    def test_multi_mode_return(self):
        contract = {
            "returns": {
                "roadmap": {
                    "type": "object",
                    "required": ["status"],
                    "properties": {
                        "status": {"type": "string"},
                    },
                },
                "detail": {
                    "type": "object",
                    "required": ["status", "files"],
                    "properties": {
                        "status": {"type": "string"},
                        "files": {"type": "array"},
                    },
                },
            },
            "outputs": {},
        }
        result = validate_return(
            contract, "roadmap", '{"status": "success"}', "/tmp"
        )
        assert result["status"] == "valid"

    def test_missing_output_files(self, tmp_path):
        contract = {
            "returns": {"type": "object"},
            "outputs": {
                "required": [
                    {"path": "expected-file.txt"},
                ],
            },
        }
        result = validate_return(
            contract, None, '{"status": "success"}', str(tmp_path)
        )
        assert result["status"] == "invalid"
        assert "expected-file.txt" in result["missing_files"][0]

    def test_existing_output_files(self, tmp_path):
        (tmp_path / "expected-file.txt").write_text("content")
        contract = {
            "returns": {"type": "object"},
            "outputs": {
                "required": [
                    {"path": "expected-file.txt"},
                ],
            },
        }
        result = validate_return(
            contract, None, '{"status": "success"}', str(tmp_path)
        )
        assert result["status"] == "valid"
        assert result["missing_files"] == []

    def test_glob_output_files(self, tmp_path):
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()
        (tickets_dir / "001-feature.md").write_text("content")
        (tickets_dir / "002-bugfix.md").write_text("content")

        contract = {
            "returns": {"type": "object"},
            "outputs": {
                "required": [
                    {"path": "tickets/*.md", "min_count": 2},
                ],
            },
        }
        result = validate_return(
            contract, None, '{"status": "success"}', str(tmp_path)
        )
        assert result["status"] == "valid"

    def test_glob_output_insufficient_count(self, tmp_path):
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()
        (tickets_dir / "001-feature.md").write_text("content")

        contract = {
            "returns": {"type": "object"},
            "outputs": {
                "required": [
                    {"path": "tickets/*.md", "min_count": 3},
                ],
            },
        }
        result = validate_return(
            contract, None, '{"status": "success"}', str(tmp_path)
        )
        assert result["status"] == "invalid"
        assert len(result["missing_files"]) > 0

    def test_template_variable_paths_skipped(self, tmp_path):
        contract = {
            "returns": {"type": "object"},
            "outputs": {
                "required": [
                    {"path": "{ticket_path}"},
                ],
            },
        }
        result = validate_return(
            contract, None, '{"status": "success"}', str(tmp_path)
        )
        # Template paths should be skipped, not cause failure
        assert result["status"] == "valid"


class TestGetAgentDefinitionIncludesContract:
    """Tests that get_agent_definition returns contract content."""

    def test_includes_contract_yaml(self):
        from clasi.tools.process_tools import get_agent_definition

        result = get_agent_definition("code-monkey")
        assert "## Contract" in result
        assert "```yaml" in result
        assert "tier:" in result
        assert "allowed_tools:" in result

    def test_includes_agent_md_content(self):
        from clasi.tools.process_tools import get_agent_definition

        result = get_agent_definition("code-monkey")
        assert "Code Monkey Agent" in result
