# SPEC-judge-check.md — LLM-judge check interface (Phase 2)

The contract for extending Ringer's exit-code verification to judgment work (documents, research, briefings). A judge check is an ordinary Ringer `check` command; Ringer never knows a judge is involved.

## Interface

```
python3 checks/judge.py \
  --rubric   rubrics/<deliverable-type>.md \
  --artifact <path-to-worker-output> \
  --judge-model <model-id> \
  [--threshold 0.8] \
  [--shadow]
```

**Exit codes:** `0` = PASS (score ≥ threshold), `1` = FAIL, `2` = judge error (malformed artifact, judge unreachable) — never silently pass on error.

**Output (stdout, always printed):**

```
JUDGE: <model-id>  RUBRIC: briefing v3  SCORE: 0.62  THRESHOLD: 0.80  VERDICT: FAIL
FAILED LINES:
- R4 "Every claim cites a dated source": 3 uncited claims (paras 2, 5, 9)
- R7 "Actionable next step per section": section 'Market' has none
```

The failed-lines block is mandatory — it is what makes Ringer's single retry informed instead of blind.

## Rubric format (`rubrics/<type>.md`)

Markdown, one numbered requirement per line (`R1`, `R2`, …), each independently scoreable, each phrased so a failure can name evidence. Version header at top (`rubric: briefing v3`). One rubric per deliverable type — never a generic "quality" rubric.

## Invariants

1. **Judge ≠ producer.** The judge model is never the model (or model family, where feasible) that produced the artifact.
2. **Shadow mode before gating.** With `--shadow`, the check always exits 0 but logs `{artifact, score, verdict, rubric_version}` to `runs/judge-shadow.jsonl`. Owner verdicts are logged alongside. Gating (dropping `--shadow`) requires ≥80% judge/owner agreement over the shadow window — and applies to internal work only.
3. **Human gate on external work is permanent.** No judge score ships a prospect- or client-facing artifact.
4. **Errors fail loudly.** Exit 2 is not a pass; Ringer treats non-zero as FAIL, which is correct.
5. **Log everything.** Every judge call appends to the shadow/eval JSONL (append-only) so rubric quality and judge drift are measurable.
6. **Overrides feed the rubric.** When the owner overrides a verdict, the disagreement is logged with the rubric line at issue; recurring disagreements trigger a rubric revision (bump version).

## Open items

- Judge model selection: cheap judge vs. frontier judge per deliverable type — decide from shadow-mode agreement data, not price alone.
- Calibration set: optionally seed with known-good / known-bad past deliverables before shadow mode to fail fast on a useless rubric.
