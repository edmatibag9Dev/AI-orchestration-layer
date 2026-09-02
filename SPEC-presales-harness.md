# SPEC-presales-harness.md — Phase 3, first harness

**Status:** DESIGN (2026-07-31) · **Build scope decided:** vertical slice — Stage 3 only
**Layer:** L3 (harness) · **Runtime:** Claude Agent SDK (Python, `claude-agent-sdk`), hosted locally
**Depends on:** L1 Ringer (dispatch + eval log), `SPEC-judge-check.md`, `ESCALATION-POLICY.md`

---

## 1. What this harness is

One hardened workflow: the vendor RFP/RFI/RFQ Functional & Gap Analysis. It does **not**
reimplement that pipeline. The Agent SDK auto-loads skills from `~/.claude/` and `.claude/`,
so the harness orchestrates the existing `<vendor>-rfp-gap-analysis` skill (plus
`heavy-file-ingestion` and `docx`) and adds the four things a skill cannot enforce:

1. **Fixed stage order**, owned by Python — the model does stage work, never stage control.
2. **Draft-only tool policies**, enforced by a `can_use_tool` callback, not by prose.
3. **An artifact store** — every stage's input and output persisted, and cross-run memory.
4. **Mechanical verification** of the one rule the deliverable lives or dies on: every
   capability claim resolves to a real citation in the capability library.

**The skill stays canonical.** RAG definitions, rating rules, and the prospect-facing rules
live in `SKILL.md` at `<LIBRARY_ROOT>`. When a rule changes, it changes in one
place. The harness supplies sequencing, gates, dispatch, and proof.

### Why the Agent SDK and not Managed Agents

Managed Agents would supply the harness *and* the deployment, plus Outcomes (a rubric-graded
iterate loop) and server-enforced `always_ask` tool gates — a genuinely close fit on paper.
It loses on one fact: **prospect RFPs are confidential client material**, and the whole
pipeline is local (knowledge repo, brand template, Ringer, `checks/judge.py`, Open Brain).
CMA means uploading prospect documents to a hosted sandbox. Recorded as a considered
alternative, not an unexamined default — the CMA Outcomes pattern (define "done" as a
gradeable rubric, iterate against it) is worth stealing conceptually even on the local path.

---

## 2. Stage map

```
harness/run.py  — Python driver: owns order, gates, artifact store
  stage 0  context   Tier-2 Open Brain manifest (orchestrator only; workers never read it)
  stage 1  intake    heavy-file-ingestion over prospect inputs
  stage 2  extract   numbered requirement list          ►► HUMAN GATE (accuracy)
  stage 3  rate      RAG rating per requirement          ►► RINGER FAN-OUT   ◄── THE SLICE
  stage 4  render    internal + external DOCX
  stage 5  verify    integration gate + judge (advisory) ►► HUMAN GATE (delivery)
```

Stage 3 is the only genuinely parallelizable stage — N independent requirements, each rated
against a fixed library, each with a mechanical pass/fail. Stages 0–2 and 4–5 are sequential
and human-gated; they stay in the skill for this slice and come into the harness only if the
slice proves the architecture on a live deal.

---

## 3. Stage 3 contract (the slice)

### Input adapter — exact fields, no free-form handoff

```json
{
  "run_id": "2026-07-31T09-14-02Z",
  "prospect_codename": "<CODENAME>",
  "vertical": "water | wastewater | electric | gas | public-sector",
  "library_root": "<LIBRARY_ROOT>",
  "approved_by": "ed",
  "approved_at": "2026-07-31T09:12:00-07:00",
  "requirements": [
    {"req_id": "R-001", "text": "<verbatim or tightly paraphrased>",
     "source": "<document + section/page>",
     "category": "EAM|FSM|FSM+|CWM|Platform|Integration|Implementation|Other",
     "weight": null}
  ]
}
```

### Output adapter — one record per requirement

```json
{"req_id": "R-001",
 "rating": "Green|Amber|Red",
 "capability": "<specific vendor module/feature>",
 "evidence": {"file": "SOLUTION_PATTERNS.md", "section": "<heading>", "quote": "<verbatim span from that file>"},
 "confidence": "High|Medium|Low",
 "path_to_fit": "<required for Amber and Red>",
 "internal_note": "<internal version only>",
 "confirm_with_product": false}
```

### The check — `checks/rate_check.py` (this is the product)

Exit 0 only when **all** hold; prints the failing `req_id` and reason for each violation:

1. **Completeness** — every `req_id` from the input appears exactly once. No drops, no inventions.
2. **Vocabulary** — `rating` ∈ {Green, Amber, Red}; `confidence` ∈ {High, Medium, Low}.
3. **Citation resolves** — for every Green and Amber: `evidence.file` exists under
   `library_root`, and `evidence.quote` appears **verbatim** in that file. This is the
   anti-hallucination gate. A fabricated or paraphrased citation fails here, mechanically.
4. **Path to fit** — every Amber and Red carries a non-empty `path_to_fit`.
5. **Source-of-truth rule** — no `evidence.file` resolves to a prospect document. The
   prospect's own docs are the source of requirements only, never of vendor capability.
6. **No silent Greens** — a Green with `confidence: "Low"` fails; that combination is the
   shape overstatement takes.

Rules 3 and 6 are the point of putting this stage under Ringer at all: *"overstatement is
failure"* stops being a sentence in a skill file and becomes an executed check. The skill's
accuracy doctrine is now enforceable by exit code.

### Dispatch shape

Requirements batch into groups of ~8–12 per worker task (`task_type: gap-rating`). Each task
spec is self-contained per Ringer craft rules: role, the library paths it may read, the
rating rules verbatim, the output contract, and the hard rules ("never cite a prospect
document as capability evidence"; "no library support → not Green"). Workers write to their
own task dir; the check copies validated output into the run's artifact store.

**Engine:** ask the owner at first run with the scoreboard in hand (`./ringer.py models --task-type
gap-rating` will be empty on run one — recommend from the nearest neighbour, `docs`, where
GLM is 0.76 first-try at ~1–2¢ and Codex 0.83 at ~4× the tokens). One exploration lane if
the batch has ≥3 tasks.

---

## 4. Tool policy — draft-only, enforced in code

A `can_use_tool` callback denies before the model acts. Not prompt guidance; a function.

| Rule | Enforcement |
|---|---|
| Writes confined to the run's artifact dir | Deny `Write`/`Edit` with any path outside `<run_dir>/` |
| No prospect-facing artifact before the gate | Deny any path matching `*EXTERNAL*` unless `gate-delivery.approved.json` exists |
| No outbound actions, ever | Deny every send/post/share tool (mail, Slack, Drive share) — Lane 4, permanent, no gate clears it |
| No destructive shell | Deny `rm`, `git push`, `git commit` inside stage turns |
| Library is read-only | Deny writes anywhere under `library_root` — the knowledge repo is edited by the owner, never by a stage |

Workers under Ringer inherit the sandbox plus the Phase-2.5 rule: **workers never read Open
Brain.** The orchestrator assembles context into worker specs at stage 0.

---

## 5. Human gates — file tokens, never inferred

Two gates, both hard stops, both cleared only by the owner:

- `gate-requirements.approved.json` — stage 2 → 3. The accuracy gate from the skill.
- `gate-delivery.approved.json` — stage 5 → hand-off. Prospect-facing, Lane 4: permanent,
  regardless of judge score, regardless of how clean the run looks.

The driver checks for the file. Absent = stop. **A gate is never satisfied by model
inference, and never by the fact that a stage completed** — the same rule that made the
judge's owner verdicts real (2026-07-31): a human's judgment is recorded, never synthesized.

---

## 6. Judge — advisory only in this slice

The judge is **ungraduated** (agreement 100% over 12 pairs but zero divergence opportunities —
see BUILD-PLAN Phase 2). Therefore:

- New rubric `rubrics/gap-analysis-internal.md`, scored in shadow mode.
- Judge ≠ producer: the analysis is Claude-produced, so the judge runs GLM via OpenCode.
- The judge gates **nothing** here. It scores, logs, and accumulates the divergence data
  Phase 2 still needs. The mechanical `rate_check.py` is what actually gates stage 3.

---

## 7. Integration gate (Phase-3 requirement, added 2026-07-24)

Task-level exit 0 is not build-level proof. After all batches merge, `checks/matrix_check.py`
runs the system-level check on the assembled matrix:

- Every approved requirement present exactly once across all batches (catches merge loss).
- RAG counts in any generated summary match the matrix counts.
- Every Green/Amber citation still resolves after merge.
- No internal-only field (`internal_note`, confirm-with-product list) survives into an
  external-marked artifact.

The build is not done until this passes.

## 8. Security lint (Phase-3 requirement, added 2026-07-24)

Every run ends with a mechanical scrub over emitted artifacts: real prospect names, emails,
tokens, and API keys. Committed repo content uses codenames only; real values stay in the
gitignored artifact store and `CONFIG.local.md`.

---

## 9. Artifact store and cross-run memory

```
~/Documents/Claude/harness-runs/<prospect_codename>/<run_id>/     (gitignored)
  input.requirements.json        stage 3 input adapter
  gate-requirements.approved.json
  batches/<n>/{spec.md, output.json, check.log}
  matrix.json                    merged, integration-gated
  judge.shadow.json              advisory score
  run.log                        stage timings, engine, tokens, cost
```

**The compounding asset** is `confirm-with-product.jsonl` — every requirement where the
library was ambiguous, accumulated across runs. When the owner gets an answer from vendor product,
it is promoted into `SOLUTION_PATTERNS.md` and never re-derived. That is Pattern 4
for this workload: in six months the library should answer questions it couldn't in month one,
and the rate of `confirm_with_product: true` should fall.

**Eval-log amendment goes live here.** Every failed rating task is tagged
`fault: spec | worker | check` (Phase 2.6, effective 2026-07-24, still 0 of 58 rows). Stage 3
is the first workload that writes it.

---

## 10. Exit criteria (slice)

1. One real prospect analysis run through stage 3 under the harness, end to end.
2. All rating tasks verified by `rate_check.py`; every citation resolved verbatim.
3. Integration gate passes on the merged matrix.
4. Both human gates exercised — including at least one where the owner rejects and the run stops.
5. `fault:` present on any failed row; eval rows land in the scoreboard under `gap-rating`.
6. The owner's verdict on the output vs. what the skill alone produces: **is the matrix better, or
   just more instrumented?** If it is only more instrumented, the harness is overhead — say so
   and stop rather than expanding to five stages.

**Kill signal:** if stage 3 rating turns out not to be parallel-shaped in practice (e.g. real
RFPs carry 12 requirements, not 120), the fan-out earns nothing. Rebalance to the integration
gate and citation check as a single-worker pipeline, and record that finding here.
