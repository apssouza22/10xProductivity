# Coordinator scratchpad orchestration

Use this rule for any coordinator agent that delegates tasks to specialists. 
Specialists write immutable per-delegation scratchpads; the coordinator maintains one live brief and passes explicit 
context in every task prompt. 
Specialists follow @agents/rules/subagent-scratchpad.md for how to format their output files.

## Workspace layout

Each run gets a scratchpad directory:

```
runs/<run_id>/scratchpad/
├── coordinator-brief.md              # coordinator live state (overwrite each step execution)
├── step1-<specialist-name 1>.md      # immutable snapshot per delegation
├── step1-<specialist-name 2>.md      # immutable snapshot per delegation
├── step2-<specialist-name>.md
└── ...
```

- **`<run_id>`** — stable ID for the run (e.g. `investigation_id` from an entry command). 
Mint one and create the directory before the first delegation if the caller did not supply it.
- **`coordinator-brief.md`** — current Structured Finding Brief. Overwrite after each step; it reflects current state, not a per-step log.
- **`step<N>-<specialist-name>.md`** — one file per delegation, so a step running several specialists in parallel produces one file each. 
Tell the specialist the exact path in its task prompt; it writes there itself. Never edit an earlier step's file — a new delegation gets a new path.

Never let raw logs, payloads, or full command output land in any scratchpad. Summaries and concrete citations only.

## Structured Finding Brief

Before each step, update the brief, persist it to `coordinator-brief.md`, and include it **verbatim** in every specialist task prompt for that step.
The brief plus the per-delegation question is all the specialist knows — they do not inherit the coordinator's conversation.

Required fields (use "none yet" when empty):

| Field | Purpose |
|-------|---------|
| **Task scope** | Top-level inputs for this run (e.g. service, env, symptom, time window) |
| **Current working status** | One line on where the run stands |
| **Confirmed evidence** | Established findings, each with a concrete citation |
| **Ruled out** | Excluded hypotheses and the citation(s) that excluded them |
| **Unknowns/gaps** | Unconfirmed items, missing config, or evidence that could not be gathered |
| **Unrelated/background signals** | Observations not yet tied to the task — so specialists do not re-report them as new |
| **Next step plan** | Which specialist(s) come next and why |

**Per-delegation only** (include in the task prompt, not necessarily in `coordinator-brief.md`):

| Field | Purpose |
|-------|---------|
| **Specific question** | Narrow question this delegation must answer, scoped to that specialist's tools |
| **Output scratchpad path** | Exact `step<N>-<specialist-name>.md` path this specialist must write |

After each step, fold specialist scratchpad findings into confirmed evidence, ruled out, unknowns, and background signals before delegating
again. Preserve provenance (citations) when folding — do not summarize away the source.

## Step lifecycle

A **step** is one round of delegation, and it can hold several specialist tasks running in parallel.

**Parallel within a step** — specialists are independent when each can answer from the task scope and current brief alone, without 
another specialist's scratchpad from this run. Launch them in one batched message (multiple`Agent` calls) under the same step number, 
with the same brief, and a distinct output scratchpad path per call.

**A new step** — open one only after updating the brief, when a specialist depends on prior evidence.

After every step:

1. Wait for **all** specialists in the step to finish.
2. `Read` their scratchpad files.
3. Update `coordinator-brief.md` once.
4. Delegate the next step (if any).

Never parallelize a final synthesizer/reporter specialist with evidence-gathering specialists.

## Specialist task prompt template

Every specialist task prompt must include, **in this order**:

1. The current **Structured Finding Brief**, verbatim.
2. Paths of any **prior scratchpads** relevant to this delegation (so the specialist can `Read` them for detail beyond the brief).
3. **Coordinator-specific runtime context** (optional slot — e.g. browser session name, tab index, auth status). Omit when not applicable.
4. The **specific question** for this delegation and the **exact output scratchpad path** the specialist must write.

Specialists must reason only from: (1) their task prompt, (2) the brief, (3) tool results they collect, and 
(4) prior scratchpads you pointed them at. 
Do not expect a specialist to recall anything from an earlier execution that is not in the brief or scratchpad paths you hand it this time.

