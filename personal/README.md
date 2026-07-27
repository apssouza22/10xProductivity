# Personal Workspace Moved

This folder is intentionally a placeholder.

Private runtime files no longer live inside this public repo. Use:

```text
TENX_PRIVATE_DIR=~/.incident-investigator-agent
~/.incident-investigator-agent/.env
~/.incident-investigator-agent/personal/
~/.incident-investigator-agent/verified_connections.md
```

You may override the private location by setting `TENX_PRIVATE_DIR`.

Do not put credentials, browser profiles, cookies, company-specific connection
files, or verified connection indexes in this repo folder. Keep real personal
recipes under `TENX_PRIVATE_DIR/personal/`.
