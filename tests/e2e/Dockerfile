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

# Git config (Claude Code needs this)
RUN git config --global user.email "agent@clasi-e2e.test" \
    && git config --global user.name "CLASI E2E Agent"

# Working directory
WORKDIR /project

# Entrypoint script
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Guessing game spec (baked in, no mount needed)
COPY guessing-game-spec.md /spec/guessing-game-spec.md

# API key is passed via ANTHROPIC_API_KEY env var at runtime

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]