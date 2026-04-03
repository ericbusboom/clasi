---
name: rundbat
description: Instructions for using rundbat to manage deployments, Docker containers, databases, and remote servers
---

# rundbat — Deployment and Infrastructure

Projects may use `rundbat` to manage Docker-based development
environments, databases, and remote server infrastructure.

## Getting Full Instructions

Run `rundbat mcp --help` to see all available MCP tools and their
documentation. If rundbat is configured as an MCP server in the
project, use its tools directly.

## Key Responsibilities

rundbat handles:

- **Docker containers** — provisioning, starting, stopping, inspecting
- **Databases** — creating local Postgres instances, managing connection
  strings, running migrations
- **Deployment environments** — dev, staging, prod environment setup
- **Secrets via dotconfig** — rundbat uses dotconfig under the hood for
  credential storage (SOPS-encrypted)
- **Remote servers** — Docker context management for remote hosts

## Quick Reference

```bash
rundbat init                      # Set up rundbat in the current project
rundbat env list                  # List configured environments
rundbat env connstr <name>        # Get a database connection string
rundbat mcp                       # Start the MCP server (for AI agents)
```

## Rules for Agents

1. **Use rundbat for all infrastructure operations** — do not write
   raw `docker run` or `docker compose` commands when rundbat can
   handle it.
2. **Use rundbat's MCP tools** when available — they handle credential
   management, naming conventions, and cleanup automatically.
3. **Database credentials go through dotconfig** — rundbat's
   `set_secret` tool writes secrets to the encrypted config. Never
   hardcode connection strings.
