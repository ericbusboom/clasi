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

# Claude Code (global install)
RUN npm install -g @anthropic-ai/claude-code \
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