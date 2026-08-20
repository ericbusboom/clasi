"""YAML loader for CLASI state machine definitions.

Reads ``clasi/schemas/state-machines/<name>.yaml`` via
``importlib.resources`` and constructs an in-memory :class:`Machine`
object.  This is the only module that parses state-machine YAML; no
other module in the subsystem performs I/O.
"""

from __future__ import annotations

import functools
import importlib.resources as _res
from typing import Any

import yaml

from clasi.state_machine.models import Machine, MachineSyntaxError, State, Transition

# Top-level keys required in every machine YAML file.
_REQUIRED_KEYS: tuple[str, ...] = ("machine", "context", "initial", "states")


@functools.lru_cache(maxsize=None)
def load_machine(name: str) -> Machine:
    """Load a named state machine from the package YAML data files.

    Resolves ``clasi/schemas/state-machines/<name>.yaml`` via
    :func:`importlib.resources.files`, parses it with
    :func:`yaml.safe_load`, and constructs the :class:`Machine` object.

    As of sprint 026, this is wrapped with ``functools.lru_cache`` — the
    three packaged machine names (``"project"``, ``"sprint"``,
    ``"ticket"``) are the entire keyspace, and the packaged YAML never
    changes within a running process, so each name is parsed once per
    process rather than once per call (a single status-inject invocation
    previously re-parsed the same three files about 20 times). The cache
    is process-lifetime, keyed only on *name*; call
    ``load_machine.cache_clear()`` to force a fresh parse (test code that
    swaps out the underlying YAML source must do this explicitly — the
    cache is a production-path optimization, not something tests should
    rely on being disabled).

    Args:
        name: Machine name without extension — one of ``"project"``,
            ``"sprint"``, or ``"ticket"``.

    Returns:
        A fully constructed :class:`Machine` instance.

    Raises:
        FileNotFoundError: If no YAML file exists for *name*.
        MachineSyntaxError: If the YAML is syntactically invalid or
            missing required top-level keys.
    """
    resource_path = _res.files("clasi.schemas").joinpath(
        "state-machines", f"{name}.yaml"
    )

    # Resolve to a concrete path so we can give a clear error message.
    try:
        # ``as_file`` works for both installed packages (zip) and dev checkouts.
        with _res.as_file(resource_path) as path:
            if not path.exists():
                raise FileNotFoundError(
                    f"No state machine definition found for {name!r}. "
                    f"Expected file: clasi/schemas/state-machines/{name}.yaml"
                )
            raw_text = path.read_text(encoding="utf-8")
    except (TypeError, AttributeError):
        # Fallback: resource_path may already be a Traversable that raises
        # if the file does not exist; surface it as FileNotFoundError.
        raise FileNotFoundError(
            f"No state machine definition found for {name!r}. "
            f"Expected file: clasi/schemas/state-machines/{name}.yaml"
        )

    # Parse YAML.
    try:
        data = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise MachineSyntaxError(
            f"YAML syntax error in state machine {name!r}: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise MachineSyntaxError(
            f"State machine file for {name!r} must contain a YAML mapping, "
            f"got {type(data).__name__}"
        )

    # Check required top-level keys.
    for key in _REQUIRED_KEYS:
        if key not in data:
            raise MachineSyntaxError(
                f"State machine file for {name!r} is missing required key: {key!r}"
            )

    return _build_machine(data, name)


def _build_machine(data: dict[str, Any], source_name: str) -> Machine:
    """Construct a :class:`Machine` from a validated parsed dict."""
    machine_name: str = data["machine"]
    context_type: str = data["context"]
    initial: str = data["initial"]
    states_data: dict[str, Any] = data["states"]

    if not isinstance(states_data, dict):
        raise MachineSyntaxError(
            f"'states' in {source_name!r} must be a mapping, "
            f"got {type(states_data).__name__}"
        )

    states: dict[str, State] = {}
    for state_name, state_body in states_data.items():
        states[state_name] = _build_state(state_name, state_body, source_name)

    return Machine(
        name=machine_name,
        context_type=context_type,
        initial=initial,
        states=states,
    )


def _build_state(
    state_name: str, body: dict[str, Any] | None, source_name: str
) -> State:
    """Construct a :class:`State` from a single state entry in the YAML dict."""
    if body is None:
        body = {}
    if not isinstance(body, dict):
        raise MachineSyntaxError(
            f"State {state_name!r} in {source_name!r} must be a mapping, "
            f"got {type(body).__name__}"
        )

    description: str = body.get("description") or ""
    invariants: list[str] = body.get("invariants") or []
    transitions_data: dict[str, Any] = body.get("transitions") or {}

    if not isinstance(invariants, list):
        raise MachineSyntaxError(
            f"'invariants' for state {state_name!r} in {source_name!r} "
            f"must be a list, got {type(invariants).__name__}"
        )
    if not isinstance(transitions_data, dict):
        raise MachineSyntaxError(
            f"'transitions' for state {state_name!r} in {source_name!r} "
            f"must be a mapping, got {type(transitions_data).__name__}"
        )

    transitions: dict[str, Transition] = {}
    for t_name, t_body in transitions_data.items():
        transitions[t_name] = _build_transition(t_name, t_body, state_name, source_name)

    return State(
        name=state_name,
        description=str(description).strip(),
        invariants=tuple(invariants),
        transitions=transitions,
    )


def _build_transition(
    t_name: str,
    body: dict[str, Any] | None,
    state_name: str,
    source_name: str,
) -> Transition:
    """Construct a :class:`Transition` from a single transition entry."""
    if body is None:
        body = {}
    if not isinstance(body, dict):
        raise MachineSyntaxError(
            f"Transition {t_name!r} in state {state_name!r} of {source_name!r} "
            f"must be a mapping, got {type(body).__name__}"
        )

    if "to" not in body:
        raise MachineSyntaxError(
            f"Transition {t_name!r} in state {state_name!r} of {source_name!r} "
            f"is missing required key: 'to'"
        )

    to: str = body["to"]
    conditions: list[str] = body.get("conditions") or []
    action: str | None = body.get("action") or None

    if not isinstance(conditions, list):
        raise MachineSyntaxError(
            f"'conditions' for transition {t_name!r} in state {state_name!r} "
            f"of {source_name!r} must be a list, got {type(conditions).__name__}"
        )

    return Transition(
        name=t_name,
        to=to,
        conditions=tuple(conditions),
        action=action,
    )
