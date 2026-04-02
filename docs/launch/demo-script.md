# Demo Script

This runbook gives one reproducible end-to-end flow per standalone server plus one unified `Apple-Tools-MCP` flow.

## Public prompt files

- Unified flow template: [prompts/checklist-template.md](./prompts/checklist-template.md)
- Standalone flow checklist: [prompts/per-server-e2e-checklist.md](./prompts/per-server-e2e-checklist.md)

## Demo rules

- only send mail to your own test inbox
- only text yourself
- only create clearly labeled test reminders, events, notes, and contacts
- use Contacts before Mail or Messages when the target is a person
- run the health tool before the first real action on a fresh install

## Unified Apple-Tools flow

Use [prompts/checklist-template.md](./prompts/checklist-template.md) as the main public demo.

Expected coverage:
- Contacts resolution
- Mail send to self
- Messages send to self
- Reminders test creation
- Calendar read
- Notes daily and weekly digest creation
- Maps lookup and route summary
- System status capture
- recent files summary

## Standalone flows

Use [prompts/per-server-e2e-checklist.md](./prompts/per-server-e2e-checklist.md) for per-server launch checks.

Expected coverage:
- Mail, Calendar, Reminders, Messages, Contacts, Notes, Shortcuts, Files, System, and Maps

## Install-all demo path

For a single environment that installs every package together:

```bash
cd /path/to/Apple-MCPs
bash scripts/install_all.sh
```

Then point your MCP client at the installed console script in the created environment, or continue to use the per-server `start.sh` files from the repo checkout.
