rubric: morning-briefing v2
<!-- Judge-checkable from the rendered briefing HTML alone (no pipeline files).
     Source of truth: ai-briefing pipeline/briefing-prompt.md v2.5 (2026-07-22).
     Each line independently scoreable; failures must name evidence.

     LINE IDs ARE STABLE ACROSS VERSIONS. An R-number always means the same
     requirement, so shadow rows stay comparable version to version. Never
     renumber; retire a line by marking it withdrawn, add new requirements at
     the end.

     v2 (2026-07-31) — revised from 12 shadow rows (2026-07-19 .. 2026-07-30):
       R1  TIGHTENED (not loosened). v1's "2-sentence-scale" was too vague to
           apply consistently: it fired correctly on 07-28 (7- and 6-sentence
           summaries, verified against the source spec's "2-sentence summary")
           but stayed silent on 3-sentence drift on 07-23/26/29/30. The limit is
           now mechanical, and "Why it matters" takes and "Verification note"
           blocks are explicitly excluded from the count — the judge was
           counting those as part of the summary.
       R4  REWRITTEN. v1 failed any date hedge anywhere on the page, which
           contradicts the editorial spec's requirement to hedge honestly about
           a source's publication date. It fired on compliant text three times
           (07-21, 07-26, 07-30) and never on a real defect. Now scoped to
           source links and to unsupported product release/GA date claims.
       R10 EVIDENCE CONTRACT ADDED. v1's only failure (07-20) cited evidence
           that refuted itself ("verified correct. Wait: calendar check
           confirms..."). A fail now requires naming both the stated and the
           computed weekday.
     R9 unchanged: its 07-22 catch (bare unlinked tickers in take bodies) was
     verified true and is the judge's best evidence of value to date.
-->

R1. Layer 1 (Executive Summary) has at most 5 items, and every item carries all required parts: a headline, a summary, a "Why it matters" take, and a source link. The summary paragraph is at most 2 sentences — count ONLY the item's summary paragraph; never count the "Why it matters" take, and never count a "Verification note" block (those are separate blocks with their own length allowance). Any fail must name the item number and the sentence count you counted.

R2. Every "Why it matters" take speaks to the reader lens — investor (who wins/loses financially, which tickers move, sector signal) or builder/presales (usable in demos, MCP/automation work, or enterprise-AI customer conversations) — not generic news commentary.

R3. Every take connects to the AI thesis of the story (capability, adoption, regulation, competitive dynamics, or what the reader can use or sell). Generic equity commentary with no AI connection fails this line.

R4. Every item — both layers — carries a real, resolvable source link, and no item asserts a product release, GA, or availability date that its own cited source does not support. Honest hedging about a SOURCE's publication date or timing ("the SIEPR page carries no publication date", "could not be pinned to an hour inside the window") is COMPLIANT reporting and must NOT fail this line. Fail only on (a) a missing or unresolvable source link, (b) a release/GA/availability date asserted as fact that the source does not support, or (c) a literal unresolved placeholder left in the briefing's own copy ("date?", "(date unconfirmed)", a bare "TBD" sitting in a date slot).

R5. Layer 2 sections appear in canonical order (Frontier Labs, Open Source, Industry & Capital, The Discourse, AI in Business), and a light day is handled honestly: short sections stay short or say "Quiet day" — no filler items that obviously fail the significance bar.

R6. Significance bar holds: no routine benchmark-win items, no sub-$100M funding without an explicit strategic reason, no vendor marketing fluff, and no anonymous-survey claims (e.g. "73% of executives say…") as items.

R7. Thesis discipline: any take that leans on a standing thesis names it explicitly (T1–T8), and evidence cutting AGAINST a thesis is led with a warning framing (e.g. "⚠ cuts against…") rather than buried after confirming evidence.

R8. Voice: compressed, analyst-grade, opinionated takes specific enough to be wrong; no hype vocabulary ("game-changer", "revolutionary", "groundbreaking", "stunning").

R9. Tickers are $-prefixed and each is hyperlinked to its Yahoo Finance quote page; no bare, unlinked ticker symbols in items that name public companies' stock moves.

R10. Date integrity: the page's stated weekday matches the weekday its stated calendar date actually fell on. Evidence for this line must name BOTH the weekday the page states AND the weekday you computed from that calendar date. If the two agree, the line passes — never fail this line without naming a concrete mismatch between the two.
