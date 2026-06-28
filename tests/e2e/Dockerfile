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

# clasi — spec-driven dev system under test
RUN pip install --no-cache-dir \
    git+https://github.com/ericbusboom/clasi.git

# Entrypoint script (copy as root first)
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Guessing game spec (baked in, no mount needed)
COPY guessing-game-spec.md /spec/guessing-game-spec.md

# Create non-root user (Claude refuses --dangerously-skip-permissions as root)
RUN useradd -m -s /bin/bash agent && \
    mkdir -p /project && \
    chown -R agent:agent /project

# Switch to non-root user
USER agent
WORKDIR /project

# Git config for non-root user
RUN git config --global user.email "agent@clasi-e2e.test" \
    && git config --global user.name "CLASI E2E Agent"

# API key is passed via ANTHROPIC_API_KEY env var at runtime
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]