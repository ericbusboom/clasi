"""Static regression guard for sprint-planner's plan-sizing instructions.

Sprint 020 ticket 006: sprint-planner's canonical docs previously had only a
binary trivial/small vs. substantial/structural sizing decision. A sprint
that added one new module (no new cross-module dependency, no data-model
change) still counted as "substantial" because it introduced a new
component, which forced the full 7-step methodology including a "Required"
Mermaid component diagram (see the old agent.md Step 4 and
architecture-authoring SKILL.md Step 4, both of which said "Required Mermaid
diagrams" with the component diagram unconditional). That produced
1,300-2,300 word plans with a diagram for a trivial 3-game stdlib CLI, one
module per sprint.

The fix adds a third "compact" tier with concrete, checkable criteria
(module count, cross-module dependency change, dependency-direction change,
data-model change) so a single-module addition gets a diagram-free,
naturally-short Architecture section, while sprints that genuinely touch 3+
modules or change dependencies still get the full treatment.

These tests are a STATIC DOC-CONTENT check, not a behavioral test: they
assert the canonical instructions say the right thing (three tiers exist,
diagrams are conditioned on concrete criteria rather than automatic, a
compact/substantial worked example is cited), not that an actual planner
run produces a proportionate document. Plan-writing judgment can't be
exercised by pytest -- there's no function call to assert against, only
prose an LLM agent reads. This is the same category of guard as
TestIssueLinkageInstructionsPresent in test_issue_lifecycle.py, and shares
its accessor pattern (Project.get_agent, the same content-loading path
CLASI itself uses).
"""

from pathlib import Path


def _agent_definition(name: str) -> str:
    from clasi.project import Project

    # Project() only needs a valid root for path resolution here; the
    # agents directory is packaged, not project-scoped.
    proj = Project(Path.cwd())
    return proj.get_agent(name).definition


def _architecture_authoring_skill_text() -> str:
    from clasi.project import Project

    proj = Project(Path.cwd())
    # Skills live as a sibling of agents/ under plugin/, same packaged
    # resolution style as Project._agents_dir uses for agents.
    skill_path = (
        proj._agents_dir.parent / "skills" / "architecture-authoring" / "SKILL.md"
    )
    assert skill_path.exists(), (
        f"architecture-authoring SKILL.md not found at {skill_path}"
    )
    return skill_path.read_text(encoding="utf-8")


class TestThreeTierSizingDecisionPresent:
    """The Effort Decision must define three tiers, not two, with concrete
    criteria for the middle tier -- not just a word-count target."""

    def test_agent_md_effort_decision_has_compact_tier(self):
        text = _agent_definition("sprint-planner")
        effort_start = text.index("Effort Decision")
        workflow_start = text.index("## Workflow")
        effort_section = text[effort_start:workflow_start]

        assert "Compact" in effort_section, (
            "sprint-planner agent.md's Effort Decision must define a "
            "'Compact' tier distinct from Trivial/small and "
            "Substantial/structural -- a binary decision forces any sprint "
            "that adds a new module into the substantial (diagram-required) "
            "path even when it introduces no new cross-module dependency"
        )
        # The tier must be judged by concrete, checkable signals -- not a
        # bare word-count target, per the ticket's explicit warning that a
        # word-count-only rule invites padding or truncation.
        assert "cross-module dependency" in effort_section, (
            "Compact tier criteria must reference cross-module dependency "
            "as a disqualifying signal"
        )
        assert "data-model change" in effort_section or "data model change" in (
            effort_section
        ), "Compact tier criteria must reference data-model change as a disqualifying signal"
        assert "module count" in effort_section or "modules touched" in effort_section, (
            "Sizing criteria must reference module count as a judgeable signal"
        )

    def test_agent_md_does_not_gate_solely_on_word_count(self):
        text = _agent_definition("sprint-planner")
        effort_start = text.index("Effort Decision")
        workflow_start = text.index("## Workflow")
        effort_section = text[effort_start:workflow_start]

        assert "not a truncation target" in effort_section or (
            "not a target" in effort_section
        ), (
            "the word-count guideline (roughly 300-500 words) must be framed "
            "as a natural consequence of scope, not a hard target -- "
            "otherwise it can be gamed by padding or truncating prose"
        )

    def test_skill_md_effort_decision_has_compact_tier(self):
        text = _architecture_authoring_skill_text()
        assert "Compact" in text, (
            "architecture-authoring SKILL.md must define a Compact sizing "
            "tier alongside Trivial/small and Substantial/structural"
        )
        assert "cross-module dependency" in text
        assert "module count" in text


class TestDiagramsConditionalNotDefault:
    """The component/module diagram must be conditioned on concrete
    criteria (module count, new dependency), not produced unconditionally
    whenever a sprint is above the trivial tier."""

    def test_agent_md_step_4_conditions_component_diagram(self):
        text = _agent_definition("sprint-planner")
        step4_start = text.index("Step 4: Produce Diagrams")
        step5_start = text.index("Step 5: Complete the Document")
        step4_section = text[step4_start:step5_start]

        assert "3+ modules" in step4_section or "3 modules" in step4_section, (
            "Step 4 must state the component diagram is required based on "
            "a module-count threshold, not unconditionally for every "
            "substantial sprint"
        )
        assert "omit" in step4_section.lower(), (
            "Step 4 must describe a real path to omitting the component "
            "diagram when it wouldn't clarify anything, with a stated reason"
        )

    def test_agent_md_compact_tier_omits_all_diagrams_by_rule(self):
        text = _agent_definition("sprint-planner")
        effort_start = text.index("Effort Decision")
        workflow_start = text.index("## Workflow")
        effort_section = text[effort_start:workflow_start]
        assert "no Mermaid diagrams" in effort_section, (
            "the Compact tier definition must state no Mermaid diagrams "
            "are produced -- this is the concrete behavior change from the "
            "old binary model, where 'adds a module' always meant "
            "'substantial' and diagrams were unconditionally required"
        )

    def test_skill_md_step_4_conditions_diagrams_and_covers_compact(self):
        text = _architecture_authoring_skill_text()
        step4_start = text.index("### 4. Produce Diagrams")
        step5_start = text.index("### 5. Complete the Document")
        step4_section = text[step4_start:step5_start]

        assert "3+ modules" in step4_section, (
            "SKILL.md Step 4 must condition the component diagram on a "
            "module-count threshold"
        )
        assert "compact" in step4_section.lower(), (
            "SKILL.md Step 4 must state that a compact-tier update omits "
            "all diagrams"
        )

    def test_quality_checks_no_longer_unconditionally_require_diagrams(self):
        text = _architecture_authoring_skill_text()
        checks_start = text.index("## Quality Checks")
        checks_section = text[checks_start:]

        # The old text was the bare line "Mermaid diagrams included" with
        # no qualifier -- assert it is now qualified by tier.
        assert "compact" in checks_section.lower(), (
            "Quality Checks must distinguish diagram expectations by tier "
            "(compact tier omits diagrams by rule, substantial tier "
            "requires them unless a reason is stated)"
        )


class TestProportionalityExamplesCited:
    """Regression: the guidance must preserve full treatment for genuinely
    architectural sprints, citing a real sprint as the still-gets-full-
    treatment example, and must not flatten every sprint to one size."""

    def test_agent_md_cites_018_as_substantial_example(self):
        text = _agent_definition("sprint-planner")
        effort_start = text.index("Effort Decision")
        workflow_start = text.index("## Workflow")
        effort_section = text[effort_start:workflow_start]
        assert "Sprint 018" in effort_section or "018" in effort_section, (
            "the Effort Decision section must cite sprint 018 (or an "
            "equivalently substantial sprint) as a worked example that "
            "still gets full treatment under the new tiering"
        )

    def test_agent_md_cites_020_as_diagram_omission_example(self):
        text = _agent_definition("sprint-planner")
        effort_start = text.index("Effort Decision")
        workflow_start = text.index("## Workflow")
        effort_section = text[effort_start:workflow_start]
        assert "020" in effort_section or "Sprint 020" in effort_section, (
            "the Effort Decision section should cite sprint 020 as the "
            "worked example of a sprint that is substantial by module "
            "count but reasonably omits the diagram -- proving the rule "
            "isn't a blunt 'more than N files means diagram'"
        )
