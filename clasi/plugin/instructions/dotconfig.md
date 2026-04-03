---
name: dotconfig
description: Instructions for using dotconfig to manage environment configuration — .env files, secrets, and config file storage
---

# dotconfig — Environment Configuration

Projects may use `dotconfig` to manage layered environment configuration
(.env files, SOPS-encrypted secrets, and per-developer local overrides).

## Getting Full Instructions

Run `dotconfig agent` to get complete operational instructions including
commands, directory layout, rules, and common tasks. Always do this
before working with configuration.

## Key Rules

1. **Never edit files under `config/` directly** — use `dotconfig save`
   so encryption is handled correctly.
2. **Never delete section markers or metadata comments** in `.env`.
3. **Always load before saving** if `.env` may be stale.
4. **Do not commit `.env`** — it is a generated file.
5. Use `--stdout` to read config without writing files.
6. Use `--file` with `-d` or `-l` to load/save YAML and JSON configs.

## Quick Reference

```bash
dotconfig agent                          # Full agent instructions
dotconfig load -d dev -l alice           # Assemble .env
dotconfig load -d dev --file app.yaml --stdout  # Read a file
dotconfig save                           # Write .env back to sources
dotconfig save -d dev --file app.yaml    # Store a file
dotconfig keys                           # Check encryption key status
```
