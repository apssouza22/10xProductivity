# Subagent scratchpad discipline

You do not inherit the coordinator's conversation. Reason only from your task
prompt, the Structured Finding Brief it includes, tool results you collect,
and any prior scratchpad paths the coordinator points you at.

## When to write

- Use `Write` to write to the scratchpad under `runs/<run_id>/scratchpad/`. Write there **before** returning
  findings.
- **Standalone question:** skip the scratchpad unless the task prompt names a
  path.

Path convention (assigned by the coordinator): `runs/<run_id>/scratchpad/step<N>-<subagent-name>.md`
(e.g. `step1-metrics-analyst.md`). Each file is an immutable snapshot for that delegation — never edit an earlier step's file.
Other specialists may be running in parallel in the same step, so write only to the path you were given.

If the task prompt lists prior scratchpad paths, `Read` them first so you do not re-run tasks.

## Required sections

Write a concise Markdown scratchpad including these sections, but not limited to these sections:
- **Key findings** — bullet list; each item must cite concrete provenance.
- **Unknowns/gaps** — connectivity failures, missing config, empty panels, auth blocks, or data you could not confirm.
- **Decisions/notes** — query tiers tried, scope changes, or caveats.
- **Handoff summary** — 2–4 sentences for the coordinator and later steps.

## Content limits

- **Summaries and citations only** — never paste raw logs, API payloads, full command outputs, or other verbatim text.
- **Secrets:** log bodies are especially sensitive; excerpt only what is needed to support a finding.

## Return value

After writing the scratchpad, return a compact list of evidence items (each
with provenance) plus unknowns. The scratchpad on disk is the authoritative
record the coordinator reads between steps.
