#!/bin/bash
# CLASI E2E — Assemble one run's scattered evidence into a single report
#
# validate.sh is a pure checker; run.sh/stop.sh capture per-milestone and
# container evidence; the MCP server traces calls; the state DB records
# phase-transition history; hook_handlers.py logs guard decisions. Each of
# those (tickets 002-005) writes its own file(s) but none of them summarize
# across the others. report.sh is the assembler: a pure reader of what they
# already wrote, rendering one self-contained `run-report.md` a human can
# read top to bottom with no other artifact needed (SUC-006). It adds no
# new capture logic of its own and never modifies validate.sh's output or
# any other input file.
#
# Usage:
#   ./report.sh [--run-id <id>] [<run-id>]
#
# Run-id resolution: same contract as run.sh/stop.sh/validate.sh (the
# Run-ID Handoff Contract) — explicit --run-id/positional wins; otherwise
# resolved from e2e-project/.e2e-runs/current. Fails loudly if neither
# resolves, rather than silently reporting on the wrong run.
#
# Sources assembled (one section each, numbered to match sprint.md module
# 6 / this ticket's own list):
#   1. validate.sh output, tee'd by ticket 002 into <run-dir>/validate.txt.
#   2. run.sh per-milestone durations/exit codes, from
#      <run-dir>/<NN>-<slug>/{prompt.txt,exit-code,duration}.
#   3. Sprint phase timings, from the *subject's own* state DB
#      (<project-dir>/.clasi/.clasi.db, NOT this repo's own
#      .clasi/.clasi.db — see the section below for why), read directly
#      via `sqlite3` per sprint.md's Design Rationale decision 2 / Open
#      Question 1 (a direct read, not a live query through the subject's
#      own MCP server or clasi CLI, which will typically already be gone
#      by report time).
#   4. mcp-calls.jsonl top-N slowest calls and all failures (ticket 003).
#   5. hooks.log deny count + reasons histogram, and the denied/ payload
#      inventory (ticket 005).
#   6. Dispatch inventory from <project-dir>/.clasi/log/NNN-*.md
#      frontmatter (`duration_seconds`), independent of this sprint.
#   7. A scan of <project-dir>/.clasi/log/mcp-server.log for
#      `input_value={}` signatures (the empty-args-sentinel bug from
#      .claude/rules/tool-call-empty-args.md).
#   8. Real-app coverage report, from <run-dir>/coverage/report.txt
#      (sprint 032 ticket 007's coverage.sh — run separately, not by this
#      script; see that script's own header).
#   9. Dead-code report, from <run-dir>/dead-code-report.md — agent-
#      authored (per AGENTS.md's "Coverage & Dead-Code Report" section),
#      not produced by any script in this directory (sprint 032/007).
#
# Degrades gracefully: a missing/malformed input produces a clearly
# labeled "not available" note in that section, never a hard crash that
# loses the rest of the report — a run predating one of tickets 002-005
# (or one that simply never triggered a given kind of event, e.g. zero
# guard denials) is expected, not an error.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CANONICAL_DIR="$SCRIPT_DIR/e2e-project"
TOP_N_SLOW=10
CONTEXT_MATCHES=5

RUN_ID_OVERRIDE=""

usage() {
    echo "  Usage: ./report.sh [--run-id <id>]" >&2
}

while [ $# -gt 0 ]; do
    case "$1" in
        --run-id)
            if [ $# -lt 2 ]; then
                echo "ERROR: --run-id requires a value." >&2
                usage
                exit 1
            fi
            RUN_ID_OVERRIDE="$2"
            shift 2
            ;;
        --*)
            echo "ERROR: Unknown argument '$1'." >&2
            usage
            exit 1
            ;;
        *)
            if [ -n "$RUN_ID_OVERRIDE" ]; then
                echo "ERROR: Unknown argument '$1'." >&2
                usage
                exit 1
            fi
            RUN_ID_OVERRIDE="$1"
            shift
            ;;
    esac
done

if [ ! -e "$CANONICAL_DIR" ]; then
    echo "ERROR: $CANONICAL_DIR does not exist; run ./start.sh first." >&2
    exit 1
fi
HOST_PROJECT_DIR="$(cd -P "$CANONICAL_DIR" && pwd)"

# --- Run-id resolution: explicit --run-id/positional wins; otherwise
# .e2e-runs/current. Same contract as run.sh/stop.sh/validate.sh. Fail
# loudly rather than silently reporting on the wrong or a nonexistent run.
# (Reused verbatim from validate.sh/stop.sh/run.sh — no shared lib file
# exists in this directory, so each script carries its own copy, per
# existing convention.) ---
resolve_run_id() {
    local override="$1" project_dir="$2" current_file id
    if [ -n "$override" ]; then
        printf '%s\n' "$override"
        return 0
    fi
    current_file="$project_dir/.e2e-runs/current"
    if [ -f "$current_file" ]; then
        id="$(cat "$current_file")"
        if [ -n "$id" ]; then
            printf '%s\n' "$id"
            return 0
        fi
    fi
    return 1
}

if ! RUN_ID="$(resolve_run_id "$RUN_ID_OVERRIDE" "$HOST_PROJECT_DIR")"; then
    echo "ERROR: could not resolve a run id — no --run-id given and" >&2
    echo "  $HOST_PROJECT_DIR/.e2e-runs/current does not exist or is empty." >&2
    echo "  Run ./start.sh first, or pass --run-id <id> explicitly." >&2
    exit 1
fi

RUN_DIR="$HOST_PROJECT_DIR/.e2e-runs/$RUN_ID"
if [ ! -d "$RUN_DIR" ]; then
    echo "ERROR: run directory $RUN_DIR does not exist." >&2
    exit 1
fi

# The subject's own state DB and logs — NOT this repo's. report.sh runs on
# the host from tests/e2e/, reporting on a run of the E2E harness; the
# sprint/log evidence to report on is whatever the *subject* team-lead
# (running inside the container, driven against the bind-mounted
# e2e-project/) produced during that run. That state lives entirely under
# HOST_PROJECT_DIR/.clasi/ — a separate tree from this repo's own
# .clasi/.clasi.db and .clasi/log/, which track sprint 028's own planning
# and have nothing to do with the subject session being reported on.
SUBJECT_DB="$HOST_PROJECT_DIR/.clasi/.clasi.db"
SUBJECT_LOG_DIR="$HOST_PROJECT_DIR/.clasi/log"

REPORT_FILE="$RUN_DIR/run-report.md"

# --- Small formatting helpers ---------------------------------------------

# Standard "this section's source isn't available" note. $1 = reason,
# already a complete sentence/clause.
unavailable() {
    printf '_Not available: %s_\n\n' "$1"
}

# Escape a string for safe embedding in a markdown table cell: collapse
# embedded newlines to spaces, escape pipes, and cap length.
cell() {
    local s="$1" max="${2:-100}"
    s="${s//$'\n'/ }"
    s="${s//|/\\|}"
    if [ "${#s}" -gt "$max" ]; then
        s="${s:0:$((max - 3))}..."
    fi
    printf '%s' "$s"
}

# --- Section 1: validate.sh output (ticket 002's tee) ----------------------

section_validate() {
    echo "## 1. Validation Results (\`validate.sh\`)"
    echo
    local validate_file="$RUN_DIR/validate.txt"
    echo "Source: \`$validate_file\`"
    echo
    if [ ! -f "$validate_file" ]; then
        unavailable "\`validate.txt\` was not found in the run directory — \`validate.sh\` has not been run for this run yet (or this run predates ticket 002's tee-to-run-dir behavior)."
        return 0
    fi
    local summary
    summary="$(grep -E '^  Results:|^  Status:' "$validate_file" 2>/dev/null || true)"
    if [ -n "$summary" ]; then
        echo "Summary:"
        echo
        echo '```'
        echo "$summary"
        echo '```'
        echo
    fi
    echo "<details><summary>Full validate.sh output</summary>"
    echo
    echo '```'
    cat "$validate_file"
    echo '```'
    echo
    echo "</details>"
    echo
}

# --- Section 2: run.sh per-milestone durations/exit codes (ticket 002) ----

section_milestones() {
    echo "## 2. Milestone Runs (\`run.sh\`)"
    echo
    echo "Source: \`$RUN_DIR/<NN>-<slug>/{prompt.txt,exit-code,duration}\`"
    echo

    local dirs
    dirs="$(find "$RUN_DIR" -mindepth 1 -maxdepth 1 -type d -name '[0-9][0-9]-*' 2>/dev/null | sort || true)"
    if [ -z "$dirs" ]; then
        unavailable "no \`<NN>-<slug>\` milestone directories found under \`$RUN_DIR\` — \`run.sh\` may not have been used to drive this run (see AGENTS.md's run.sh mandate), or the run has no milestones yet."
        return 0
    fi

    local total=0 failed=0
    echo "| # | Milestone | Exit Code | Duration (s) | Prompt (truncated) |"
    echo "|---|-----------|-----------|---------------|---------------------|"
    local dir name exit_code duration prompt_line
    while IFS= read -r dir; do
        [ -z "$dir" ] && continue
        total=$((total + 1))
        name="$(basename "$dir")"
        exit_code="$(cat "$dir/exit-code" 2>/dev/null || echo "—")"
        duration="$(cat "$dir/duration" 2>/dev/null || echo "—")"
        prompt_line="$(head -n1 "$dir/prompt.txt" 2>/dev/null || echo "—")"
        if [ "$exit_code" != "0" ] && [ "$exit_code" != "—" ]; then
            failed=$((failed + 1))
        fi
        printf '| %s | %s | %s | %s | %s |\n' \
            "$total" "$(cell "$name" 40)" "$(cell "$exit_code" 10)" \
            "$(cell "$duration" 10)" "$(cell "$prompt_line" 80)"
    done <<< "$dirs"
    echo
    echo "Total milestones: $total. Non-zero exit codes: $failed."
    echo
}

# --- Section 3: sprint phase timings (ticket 004's phase_transitions) -----

section_phase_timings() {
    echo "## 3. Sprint Phase Timings (\`phase_transitions\`)"
    echo
    echo "Source: the **subject's own** state DB at \`$SUBJECT_DB\` — a"
    echo "separate SQLite file from this repo's own \`.clasi/.clasi.db\`."
    echo "Read directly via \`sqlite3\` (sprint.md's Design Rationale"
    echo "decision 2 / Open Question 1), since the subject's \`clasi\` CLI"
    echo "typically no longer has a running MCP server to query by the"
    echo "time a report is assembled."
    echo

    if ! command -v sqlite3 >/dev/null 2>&1; then
        unavailable "\`sqlite3\` is not installed on this host."
        return 0
    fi
    if [ ! -f "$SUBJECT_DB" ]; then
        unavailable "\`$SUBJECT_DB\` does not exist — the subject project has no state DB (has \`start.sh\`/\`clasi init\` run for it yet?)."
        return 0
    fi

    local rows
    if ! rows="$(sqlite3 -json "$SUBJECT_DB" \
        "SELECT sprint_id, from_phase, to_phase, at FROM phase_transitions ORDER BY at, id" 2>&1)"; then
        unavailable "querying \`phase_transitions\` failed — this run's subject DB predates ticket 004 (sprint-phase-transition-history), so the table doesn't exist yet. sqlite3 said: \`$(cell "$rows" 200)\`"
        return 0
    fi

    if [ -z "$rows" ] || [ "$rows" = "[]" ]; then
        echo "_No phase transitions recorded — the \`phase_transitions\` table exists but is empty (no sprint in this project has advanced phase yet)._"
        echo
        return 0
    fi

    local table
    if ! table="$(printf '%s' "$rows" | jq -r '
        group_by(.sprint_id)
        | map(
            to_entries as $entries
            | $entries
            | map(
                . as $e
                | ($e.value.at | strptime("%Y-%m-%dT%H:%M:%SZ") | mktime) as $ts
                | {
                    sprint_id: $e.value.sprint_id,
                    from_phase: ($e.value.from_phase // "(start)"),
                    to_phase: $e.value.to_phase,
                    at: $e.value.at,
                    elapsed: (if $e.key == 0 then null
                              else ($ts - ($entries[$e.key - 1].value.at
                                    | strptime("%Y-%m-%dT%H:%M:%SZ") | mktime))
                              end)
                  }
              )
          )
        | flatten
        | .[]
        | [.sprint_id, (.from_phase + " -> " + .to_phase), .at,
           (if .elapsed == null then "—" else "\(.elapsed)s" end)]
        | @tsv
    ' 2>&1)"; then
        unavailable "could not compute elapsed times from \`phase_transitions\` timestamps (jq/date parsing failed): \`$(cell "$table" 200)\`. Raw rows: \`$(cell "$rows" 200)\`"
        return 0
    fi

    echo "| Sprint | Transition | At | Elapsed since previous (same sprint) |"
    echo "|---|---|---|---|"
    echo "$table" | awk -F'\t' '{printf "| %s | %s | %s | %s |\n", $1, $2, $3, $4}'
    echo
}

# --- Section 4: mcp-calls.jsonl top-N slowest + all failures (ticket 003) -

section_mcp_calls() {
    echo "## 4. MCP Call Trace (\`mcp-calls.jsonl\`)"
    echo
    local trace_file="$SUBJECT_LOG_DIR/mcp-calls.jsonl"
    echo "Source: \`$trace_file\`"
    echo

    if ! command -v jq >/dev/null 2>&1; then
        unavailable "\`jq\` is not installed on this host."
        return 0
    fi
    if [ ! -f "$trace_file" ]; then
        unavailable "\`mcp-calls.jsonl\` was not found — this run predates ticket 003 (mcp-call-trace-with-durations), or the subject's MCP server was never invoked."
        return 0
    fi
    if [ ! -s "$trace_file" ]; then
        echo "_\`mcp-calls.jsonl\` exists but is empty — 0 MCP calls recorded for this project._"
        echo
        return 0
    fi

    local total failed
    if ! total="$(jq -s 'length' "$trace_file" 2>&1)" || ! failed="$(jq -s '[.[] | select(.ok == false)] | length' "$trace_file" 2>&1)"; then
        unavailable "\`mcp-calls.jsonl\` could not be parsed as JSONL (jq error): \`$(cell "${total:-$failed}" 200)\`"
        return 0
    fi
    echo "Total calls: $total. Failures: $failed."
    echo

    echo "### Top $TOP_N_SLOW slowest calls"
    echo
    echo "| Timestamp | Agent | Tool | ms | Outcome |"
    echo "|---|---|---|---|---|"
    jq -s -r --argjson n "$TOP_N_SLOW" '
        sort_by(-.ms) | .[0:$n] | .[]
        | [.ts, .agent, .tool, (.ms | tostring), (if .ok then "ok" else "FAIL" end)]
        | @tsv
    ' "$trace_file" | while IFS=$'\t' read -r ts agent tool ms outcome; do
        printf '| %s | %s | %s | %s | %s |\n' \
            "$(cell "$ts" 30)" "$(cell "$agent" 20)" "$(cell "$tool" 30)" "$ms" "$outcome"
    done
    echo

    echo "### All failed calls"
    echo
    if [ "$failed" -eq 0 ]; then
        echo "_No failed calls recorded — clean trace._"
        echo
        return 0
    fi
    echo "| Timestamp | Agent | Tool | ms | Args |"
    echo "|---|---|---|---|---|"
    jq -s -r '
        [.[] | select(.ok == false)] | .[]
        | [.ts, .agent, .tool, (.ms | tostring), (.args | tostring)]
        | @tsv
    ' "$trace_file" | while IFS=$'\t' read -r ts agent tool ms args; do
        printf '| %s | %s | %s | %s | %s |\n' \
            "$(cell "$ts" 30)" "$(cell "$agent" 20)" "$(cell "$tool" 30)" "$ms" "$(cell "$args" 80)"
    done
    echo
}

# --- Section 5: hooks.log deny histogram + denied/ payload inventory ------
# (ticket 005)

section_guard_decisions() {
    echo "## 5. Guard Decisions (\`hooks.log\` + \`denied/\`)"
    echo
    local hooks_log="$SUBJECT_LOG_DIR/hooks.log"
    local denied_dir="$SUBJECT_LOG_DIR/denied"
    echo "Source: \`$hooks_log\` (deny count + reasons histogram) and"
    echo "\`$denied_dir/\` (full denial payloads)."
    echo

    local deny_count=""
    if [ ! -f "$hooks_log" ]; then
        unavailable "\`hooks.log\` was not found — no hook has fired yet for this project (or the log dir is missing)."
    else
        local total_lines
        total_lines="$(wc -l < "$hooks_log" | tr -d ' ')"
        deny_count="$(awk '$3 == "2"' "$hooks_log" | wc -l | tr -d ' ')"
        echo "Total hook events logged: $total_lines. Denials (exit code 2): $deny_count."
        echo
        if [ "$deny_count" -eq 0 ]; then
            echo "_0 denials recorded — a clean run produced no guard denials for this project._"
            echo
        else
            echo "Denial reasons histogram (by the fixed-width reason code):"
            echo
            echo "| Count | Reason |"
            echo "|---|---|"
            awk '$3 == "2" {print $4}' "$hooks_log" | sort | uniq -c | sort -rn | \
                while read -r count reason; do
                    printf '| %s | %s |\n' "$count" "$(cell "$reason" 40)"
                done
            echo
        fi
    fi

    if [ ! -d "$denied_dir" ]; then
        if [ "$deny_count" = "0" ] || [ -z "$deny_count" ]; then
            echo "_No \`denied/\` directory — consistent with 0 denials above (it is only created on the first denial)._"
        else
            echo "_No \`denied/\` directory, but \`hooks.log\` recorded $deny_count denial(s) above — anomaly: payload capture may have failed for this run (see \`_log_hook_event\`'s exception handling in \`hook_handlers.py\`)._"
        fi
        echo
        return 0
    fi
    local payloads
    payloads="$(find "$denied_dir" -maxdepth 1 -type f -name '*.json' 2>/dev/null | sort || true)"
    if [ -z "$payloads" ]; then
        echo "_\`denied/\` exists but contains no payload files._"
        echo
        return 0
    fi
    local payload_count
    payload_count="$(printf '%s\n' "$payloads" | wc -l | tr -d ' ')"
    echo "Denial payload files captured: $payload_count."
    echo
    printf '%s\n' "$payloads" | while IFS= read -r f; do
        [ -z "$f" ] && continue
        echo "- \`$(basename "$f")\`"
    done
    echo
}

# --- Section 6: dispatch inventory from .clasi/log/NNN-*.md (independent -
# of this sprint; dispatch_log.py / handle_subagent_start's transcripts)

section_dispatch_inventory() {
    echo "## 6. Dispatch Inventory (\`.clasi/log/NNN-*.md\`)"
    echo
    echo "Source: YAML frontmatter (\`agent_type\`, \`started_at\`,"
    echo "\`stopped_at\`, \`duration_seconds\`) of each per-dispatch"
    echo "transcript directly under \`$SUBJECT_LOG_DIR/\`."
    echo

    if [ ! -d "$SUBJECT_LOG_DIR" ]; then
        unavailable "\`$SUBJECT_LOG_DIR\` does not exist."
        return 0
    fi

    local files
    files="$(find "$SUBJECT_LOG_DIR" -maxdepth 1 -type f -name '[0-9][0-9][0-9]-*.md' 2>/dev/null | sort || true)"
    if [ -z "$files" ]; then
        unavailable "no \`NNN-*.md\` dispatch transcripts found directly under \`$SUBJECT_LOG_DIR\` — no subagent has been dispatched in this project yet."
        return 0
    fi

    echo "| File | Agent Type | Started At | Duration (s) |"
    echo "|---|---|---|---|"
    printf '%s\n' "$files" | while IFS= read -r f; do
        [ -z "$f" ] && continue
        local agent_type started_at duration_s
        agent_type="$(_fm_field "$f" agent_type)"
        started_at="$(_fm_field "$f" started_at)"
        duration_s="$(_fm_field "$f" duration_seconds)"
        [ -z "$agent_type" ] && agent_type="—"
        [ -z "$started_at" ] && started_at="—"
        [ -z "$duration_s" ] && duration_s="— (not yet stopped)"
        printf '| %s | %s | %s | %s |\n' \
            "$(basename "$f")" "$(cell "$agent_type" 20)" \
            "$(cell "$started_at" 30)" "$(cell "$duration_s" 20)"
    done
    echo
}

# Extract a single top-level `key: value` field from a YAML frontmatter
# block (between the first two `---` lines). Surrounding double quotes are
# stripped. Prints nothing if the file has no frontmatter or lacks the key.
_fm_field() {
    local file="$1" key="$2"
    awk -v key="$key" '
        NR == 1 && $0 == "---" { infm = 1; next }
        infm && $0 == "---" { exit }
        infm {
            n = index($0, ":")
            if (n > 0) {
                k = substr($0, 1, n - 1)
                v = substr($0, n + 1)
                sub(/^ /, "", v)
                gsub(/^"|"$/, "", v)
                if (k == key) { print v; exit }
            }
        }
    ' "$file" 2>/dev/null
}

# --- Section 7: mcp-server.log input_value={} scan (empty-args-sentinel) --

section_empty_args_scan() {
    echo "## 7. Empty-Args-Sentinel Bug Scan (\`mcp-server.log\`)"
    echo
    local server_log="$SUBJECT_LOG_DIR/mcp-server.log"
    echo "Source: \`$server_log\`, scanned for the \`input_value={}\`"
    echo "signature documented in \`.claude/rules/tool-call-empty-args.md\`"
    echo "(the Claude Code harness bug where any empty/null tool argument"
    echo "silently drops all arguments)."
    echo

    if [ ! -f "$server_log" ]; then
        unavailable "\`$server_log\` was not found — the subject's MCP server may never have logged to this project, or the log dir differs."
        return 0
    fi

    local count
    count="$(grep -c 'input_value={}' "$server_log" 2>/dev/null || true)"
    [ -z "$count" ] && count=0
    echo "Occurrences of \`input_value={}\`: $count."
    echo
    if [ "$count" -eq 0 ]; then
        echo "_Clean run — no empty-args-sentinel signature found._"
        echo
        return 0
    fi

    echo "Showing the first $CONTEXT_MATCHES match(es) with 2 lines of context each:"
    echo
    echo '```'
    grep -n -B2 -A2 'input_value={}' "$server_log" 2>/dev/null | \
        awk -v max="$CONTEXT_MATCHES" '
            /input_value=\{\}/ { n++ }
            { print }
            n > max { exit }
        '
    echo '```'
    echo
    if [ "$count" -gt "$CONTEXT_MATCHES" ]; then
        echo "_...and $((count - CONTEXT_MATCHES)) more match(es) not shown above._"
        echo
    fi
}

# --- Section 8: real-app coverage report (ticket 032/007's coverage.sh) ---

section_coverage() {
    echo "## 8. Real-App Coverage (\`coverage.sh\`)"
    echo
    local cov_dir="$RUN_DIR/coverage"
    local report_txt="$cov_dir/report.txt"
    echo "Source: \`$report_txt\` (plus \`coverage.json\`, \`coverage.lcov\`,"
    echo "and \`html/index.html\` alongside it in \`$cov_dir/\`)."
    echo
    if [ ! -f "$report_txt" ]; then
        unavailable "\`coverage/report.txt\` was not found in the run directory — \`./coverage.sh\` has not been run for this run yet (or this run predates sprint 032 ticket 007's coverage harness). Run \`./coverage.sh\` after the run to produce it."
        return 0
    fi
    echo "This measures the **real application** — unlike the unit gate's"
    echo "\`pyproject.toml\` config, this report does not omit"
    echo "\`cli.py\`/\`hook_handlers.py\`/\`mcp_server.py\` (see"
    echo "\`tests/e2e/.coveragerc\`'s own header for why the two configs are"
    echo "kept deliberately separate)."
    echo
    echo "<details><summary>Full coverage report</summary>"
    echo
    echo '```'
    cat "$report_txt"
    echo '```'
    echo
    echo "</details>"
    echo
}

# --- Section 9: dead-code report (agent-authored, not script-generated) ---

section_dead_code() {
    echo "## 9. Dead-Code Report (\`dead-code-report.md\`)"
    echo
    local dc_file="$RUN_DIR/dead-code-report.md"
    echo "Source: \`$dc_file\` — agent-authored (see \`AGENTS.md\`'s"
    echo "\"Coverage & Dead-Code Report\" section), ranking \`src/clasi\`"
    echo "code never executed by either this run's real-app coverage"
    echo "(section 8 above) or the unit suite's own coverage."
    echo
    echo "**This report is a deliverable only.** Nothing in this harness"
    echo "acts on it, deletes code from it, or files an issue from it —"
    echo "any removal decision is the developer's, made later, outside"
    echo "this harness (see the source issue's Part B, and sprint 032's"
    echo "own human-in-the-loop constraint on this exact report)."
    echo
    if [ ! -f "$dc_file" ]; then
        unavailable "\`dead-code-report.md\` was not found in the run directory — this step is agent-authored and has not been produced for this run yet (or this run predates sprint 032 ticket 007)."
        return 0
    fi
    echo "<details><summary>Full dead-code report</summary>"
    echo
    cat "$dc_file"
    echo
    echo "</details>"
    echo
}

# --- Assemble --------------------------------------------------------------

main() {
    {
        echo "# E2E Run Report — $RUN_ID"
        echo
        echo "Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ) by \`tests/e2e/report.sh\`."
        echo
        echo "- Project dir: \`$HOST_PROJECT_DIR\`"
        echo "- Run dir: \`$RUN_DIR\`"
        echo
        echo "This report assembles evidence already produced by the E2E"
        echo "harness and the subject's own CLASI logs/state DB into one"
        echo "self-contained record of this run — no other artifact is"
        echo "needed to interpret it. It is a pure reader: nothing below"
        echo "was computed by re-running any check (\`validate.sh\` stays"
        echo "the sole checker; this file only reads its tee'd output),"
        echo "and no section here can affect the run it describes. A"
        echo "section reading \"Not available\" means its upstream source"
        echo "file/table was missing for this run, not that this script"
        echo "failed — see that section's note for the specific reason."
        echo

        section_validate || echo "_Section 1 crashed unexpectedly; see report.sh's stderr for details._"
        section_milestones || echo "_Section 2 crashed unexpectedly; see report.sh's stderr for details._"
        section_phase_timings || echo "_Section 3 crashed unexpectedly; see report.sh's stderr for details._"
        section_mcp_calls || echo "_Section 4 crashed unexpectedly; see report.sh's stderr for details._"
        section_guard_decisions || echo "_Section 5 crashed unexpectedly; see report.sh's stderr for details._"
        section_dispatch_inventory || echo "_Section 6 crashed unexpectedly; see report.sh's stderr for details._"
        section_empty_args_scan || echo "_Section 7 crashed unexpectedly; see report.sh's stderr for details._"
        section_coverage || echo "_Section 8 crashed unexpectedly; see report.sh's stderr for details._"
        section_dead_code || echo "_Section 9 crashed unexpectedly; see report.sh's stderr for details._"
    } > "$REPORT_FILE"

    echo "=== report.sh: run $RUN_ID ==="
    echo "  Report written: $REPORT_FILE"
}

main
