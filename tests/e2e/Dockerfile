# CLASI E2E Test Environment
# Python 3.14 + Claude Code + clasi + tmux for interactive agent testing

FROM python:3.14-slim

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    tmux \
    curl \
    ca-certificates \
    gnupg \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Node.js 22.x (required by Claude Code)
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Claude Code (global install, pinned — see commit message for how this
# version was chosen; bump deliberately, not via an unpinned `npm install`).
RUN npm install -g @anthropic-ai/claude-code@2.1.237 \
    && claude --version

# clasi — spec-driven dev system under test.
# CLASI_SOURCE selects what gets installed (build-arg, so the image is
# reproducible and the choice is recorded in `docker history`):
#   - a git ref (tag/branch/sha):
#       docker build --build-arg CLASI_SOURCE=v0.20260715.3 tests/e2e
#   - the local working tree, via a wheel in the build context:
#       uv build --wheel && cp dist/clasi-*.whl tests/e2e/clasi-local.whl
#       docker build --build-arg CLASI_SOURCE=local tests/e2e
# The [l] glob makes the COPY a no-op when no wheel is present, so git-ref
# builds don't require one.
ARG CLASI_SOURCE=local
# Local-wheel path: copy any clasi-*.whl present in the build context (the
# [w] glob makes this a no-op when none is; git-ref builds need no wheel).
# Keep the wheel's real PEP 427 filename — pip validates it, and renaming
# would also lie to clasi's own staleness/version checks.
COPY clasi-*.wh[l] /tmp/
RUN if [ "$CLASI_SOURCE" = "local" ]; then \
        pip install --no-cache-dir /tmp/clasi-*.whl; \
    else \
        pip install --no-cache-dir \
            "git+https://github.com/ericbusboom/clasi.git@${CLASI_SOURCE}"; \
    fi \
    && rm -f /tmp/clasi-*.whl \
    && clasi --version

# Entrypoint script (copy as root first)
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Guessing game spec (baked in, no mount needed)
COPY guessing-game-spec.md /spec/guessing-game-spec.md

# Coverage instrumentation for the occasional, developer-triggered e2e run
# under coverage (ticket 032/007; SUC-006 — see
# clasi/issues/test-system-improvements-real-app-coverage-from-the-e2e-a-leaner-faster-suite.md).
# `coverage` is already installed above as a transitive dependency of
# clasi's own `pytest-cov` dependency, including its subprocess-auto-start
# `.pth` hook — no separate `pip install coverage` step is needed here.
# Setting these two env vars container-wide (not just inside
# entrypoint.sh's own process tree) is what turns that dormant hook on for
# every `clasi` CLI invocation via `docker exec` AND the long-lived `clasi
# mcp` server (spawned via .mcp.json, which inherits this same env).
# Placed AFTER the `clasi --version` build-time check above so the image
# build itself never tries to write into /project/.e2e-coverage, which
# only exists once the bind mount is live at `docker run` — not at build
# time.
COPY .coveragerc /etc/clasi-e2e/.coveragerc
ENV COVERAGE_PROCESS_START=/etc/clasi-e2e/.coveragerc
ENV COVERAGE_FILE=/project/.e2e-coverage/.coverage

# Create non-root user (Claude refuses --dangerously-skip-permissions as root)
RUN useradd -m -s /bin/bash agent && \
    mkdir -p /project /home/agent/.claude && \
    chown -R agent:agent /project /home/agent/.claude

# Switch to non-root user
USER agent
WORKDIR /project

# Git config for non-root user
RUN git config --global user.email "agent@clasi-e2e.test" \
    && git config --global user.name "CLASI E2E Agent"

# Auth is passed at runtime: either ANTHROPIC_API_KEY (OpenRouter) env vars,
# or a read-only bind-mounted OAuth credentials file at
# /home/agent/.claude/.credentials.json (E2E_AUTH=subscription in start.sh).
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]