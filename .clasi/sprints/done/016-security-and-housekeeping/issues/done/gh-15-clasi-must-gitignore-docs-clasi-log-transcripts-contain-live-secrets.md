---
status: done
github-issue: ericbusboom/clasi#15
sprint: '016'
tickets:
- 016-001
---

# CLASI must gitignore docs/clasi/log/ — transcripts contain live secrets

> Imported from [ericbusboom/clasi#15](https://github.com/ericbusboom/clasi/issues/15)
## Summary

CLASI writes conversation transcripts to `docs/clasi/log/` but does **not** add that directory to the project's `.gitignore`. Because these transcripts capture raw tool results — including the contents of `.env` / dotconfig files — they routinely contain **live secrets**. With no ignore rule, a routine `git add -A` sweeps hundreds of transcript files (and their embedded secrets) into a commit.

CLASI should ensure `docs/clasi/log/` is gitignored when it initializes/writes logs in a project.

## Impact (real incident)

In a downstream project (`league-infrastructure/student-accounts`), a version-bump commit accidentally staged 237 untracked `docs/clasi/log/*.md` files. Two of them contained real secrets harvested from a dotconfig read:

- Google OAuth Client ID + Client Secret
- Anthropic API key + Admin API key
- (also present but not flagged by GitHub: GitHub OAuth secret, Pike13 client secret, `SESSION_SECRET`, Workspace temp password)

The push was only stopped by **GitHub Push Protection**. Without that safety net, live credentials would have been published.

## Root cause

- `docs/clasi/log/` is not in `.gitignore`.
- `.gitignore` only blocks *untracked* files and never untracks already-committed ones, so adding the rule after the fact still requires `git rm --cached`. The ignore rule needs to exist **before** the first log is written.

## Suggested fix

1. When CLASI initializes a project (or first writes to `docs/clasi/log/`), ensure `.gitignore` contains:
   ```gitignore
   # CLASI conversation transcripts — may contain secrets, never commit
   docs/clasi/log/
   ```
2. Make this idempotent (append only if the rule is absent).
3. Optional hardening: redact obvious secret patterns (`sk-ant-*`, `GOCSPX-*`, `*_SECRET=`, etc.) when persisting transcripts, as defense-in-depth for users who deliberately track logs.

## Workaround applied downstream

```sh
git rm --cached -r docs/clasi/log/
printf '\n# CLASI conversation transcripts — may contain secrets, never commit\ndocs/clasi/log/\n' >> .gitignore
git commit --amend
```
