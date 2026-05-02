---
description: Never commit secrets to the repository.
claude: {}
codex: {}
copilot:
  applyTo: "**"
---

Do not write API keys, passwords, tokens, or other secrets into source
files. Use environment variables or a secrets manager. If you find a
secret already committed, alert the user immediately and recommend
rotation.
