#!/usr/bin/env python3
"""Stage-3 rating check — SPEC-presales-harness.md §3.

The product of the presales harness. Turns the pipeline's central doctrine —
*overstatement is failure* — into an exit code:

    python3 checks/rate_check.py --input <requirements.json> \
        --output <ratings.json | dir> --library-root <path>

Exit 0 only when every rule below holds. Every failure prints the req_id and
why, because the failure text is what feeds the Ringer retry prompt.

  1 completeness      every input req_id rated exactly once; nothing invented
  2 vocabulary        rating/confidence inside the allowed sets
  3 citation resolves Green/Amber evidence.quote appears VERBATIM in the cited
                      library file (the anti-hallucination gate)
  4 path to fit       every Amber/Red carries one
  5 source of truth   no evidence resolves outside the capability library
                      (prospect docs are requirements-only, never capability)
  6 no silent Greens  Green + Low confidence is the shape overstatement takes

Citation targets may be .md/.txt or .docx (extracted with the stdlib — no
dependency). A citation whose target cannot be read as text FAILS rule 3
rather than passing unverified: an unverifiable claim is exactly what this
check exists to stop.
"""
import argparse
import html
import json
import os
import re
import sys
import zipfile

RATINGS = {"Green", "Amber", "Red"}
CONFIDENCE = {"High", "Medium", "Low"}
NEEDS_EVIDENCE = {"Green", "Amber"}
NEEDS_PATH = {"Amber", "Red"}


def die(code, msg):
    print(msg)
    sys.exit(code)


# ---------------------------------------------------------------- text access

def _docx_text(path):
    """Extract text from a .docx with the stdlib only.

    A docx is a zip; the body text lives in word/document.xml as <w:t> runs.
    Runs split mid-sentence, so paragraphs are joined before matching.
    """
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", errors="replace")
    xml = xml.replace("</w:p>", "\n</w:p>")          # paragraph boundaries
    xml = re.sub(r"<w:(?:tab|br)\b[^>]*/>", " ", xml)  # tabs and line breaks
    # `<w:t>` or `<w:t xml:space="preserve">` only — NOT <w:tbl>, <w:tcPr>, <w:tab>.
    parts = re.findall(r"<w:t(?:\s[^>]*)?>(.*?)</w:t>|(\n)", xml, re.S)
    return html.unescape("".join(a or b for a, b in parts))


def read_text(path):
    """Return (text, None) or (None, reason-it-could-not-be-read)."""
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext in (".md", ".txt", ".json", ".csv", ""):
            return open(path, errors="replace").read(), None
        if ext == ".docx":
            return _docx_text(path), None
        return None, f"unsupported citation target type '{ext}' (cite a .md/.txt/.docx source)"
    except (OSError, zipfile.BadZipFile, KeyError) as e:
        return None, f"could not read citation target: {e}"


def norm(s):
    """Whitespace- and quote-insensitive normalization for verbatim matching."""
    s = s.replace("’", "'").replace("‘", "'")
    s = s.replace("“", '"').replace("”", '"')
    s = s.replace("–", "-").replace("—", "-").replace(" ", " ")
    return re.sub(r"\s+", " ", s).strip()


def nospace(s):
    """Whitespace-free form — the retry used for .docx run-boundary artifacts."""
    return re.sub(r"\s+", "", norm(s))


# ---------------------------------------------------------------- rule engine

def load_records(output_path):
    """Accept a single JSON file (list or {records:[...]}) or a directory of them."""
    paths = []
    if os.path.isdir(output_path):
        for root, _, files in os.walk(output_path):
            paths += [os.path.join(root, f) for f in sorted(files) if f.endswith(".json")]
    else:
        paths = [output_path]
    records = []
    for p in paths:
        try:
            data = json.load(open(p))
        except (OSError, json.JSONDecodeError) as e:
            die(2, f"CHECK ERROR: cannot parse {p}: {e}")
        if isinstance(data, dict):
            data = data.get("records") or data.get("ratings") or []
        if not isinstance(data, list):
            die(2, f"CHECK ERROR: {p} is not a list of rating records")
        for r in data:
            r["_source_file"] = p
        records += data
    return records


def check(requirements, records, library_root):
    """Return a list of (req_id, rule, reason) failures."""
    fails = []
    lib = os.path.realpath(os.path.expanduser(library_root))
    want = [r["req_id"] for r in requirements]
    seen = {}
    for rec in records:
        seen.setdefault(rec.get("req_id", "<missing req_id>"), []).append(rec)

    # rule 1 — completeness
    for rid in want:
        n = len(seen.get(rid, []))
        if n == 0:
            fails.append((rid, "R1-completeness", "not rated — dropped by the worker"))
        elif n > 1:
            fails.append((rid, "R1-completeness", f"rated {n} times (duplicate records)"))
    for rid in seen:
        if rid not in want:
            fails.append((rid, "R1-completeness",
                          "rated but not in the approved requirement list (invented)"))

    text_cache = {}
    for rid in want:
        for rec in seen.get(rid, []):
            rating = rec.get("rating")
            conf = rec.get("confidence")

            # rule 2 — vocabulary
            if rating not in RATINGS:
                fails.append((rid, "R2-vocabulary", f"rating {rating!r} not in {sorted(RATINGS)}"))
                continue
            if conf not in CONFIDENCE:
                fails.append((rid, "R2-vocabulary",
                              f"confidence {conf!r} not in {sorted(CONFIDENCE)}"))

            # rule 6 — no silent Greens
            if rating == "Green" and conf == "Low":
                fails.append((rid, "R6-silent-green",
                              "Green asserted at Low confidence — downgrade to Amber "
                              "'needs confirmation' or supply direct evidence"))

            # rule 4 — path to fit
            if rating in NEEDS_PATH and not str(rec.get("path_to_fit") or "").strip():
                fails.append((rid, "R4-path-to-fit",
                              f"{rating} with no path_to_fit — every gap needs a route forward"))

            if rating not in NEEDS_EVIDENCE:
                continue

            ev = rec.get("evidence") or {}
            ev_file, quote = ev.get("file"), ev.get("quote")
            if not ev_file or not quote:
                fails.append((rid, "R3-citation",
                              f"{rating} with no evidence.file/evidence.quote — "
                              "no library support means not Green"))
                continue

            # rule 5 — source of truth (resolve, then confine to the library)
            cand = os.path.expanduser(ev_file)
            cand = cand if os.path.isabs(cand) else os.path.join(lib, cand)
            cand = os.path.realpath(cand)
            if os.path.commonpath([cand, lib]) != lib:
                fails.append((rid, "R5-source-of-truth",
                              f"evidence.file {ev_file!r} resolves outside the capability "
                              "library — prospect documents are the source of requirements "
                              "only, never of vendor capability"))
                continue
            if not os.path.exists(cand):
                fails.append((rid, "R3-citation",
                              f"cited file does not exist in the library: {ev_file!r}"))
                continue

            # rule 3 — the quote must appear verbatim
            if cand not in text_cache:
                text_cache[cand] = read_text(cand)
            body, err = text_cache[cand]
            if body is None:
                fails.append((rid, "R3-citation", f"{ev_file}: {err}"))
                continue
            # Verbatim match. The whitespace-stripped retry exists because .docx run
            # boundaries can drop or add spaces during extraction ("WordOne""WordTwo"),
            # which would fail a correctly-copied quote for a reason that is not
            # hallucination. The character sequence must still be present, so the
            # anti-hallucination property is unchanged.
            if norm(quote) not in norm(body) and nospace(quote) not in nospace(body):
                fails.append((rid, "R3-citation",
                              f"quote not found verbatim in {ev_file} — "
                              f"claimed: {norm(quote)[:110]!r}"))
    return fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="approved requirements JSON (stage-3 input adapter)")
    ap.add_argument("--output", required=True, help="rating records: a .json file or a directory")
    ap.add_argument("--library-root", default=os.environ.get("HARNESS_LIBRARY_ROOT"),
                    help="capability library root (or env HARNESS_LIBRARY_ROOT)")
    ap.add_argument("--report", help="write a JSON failure report here")
    a = ap.parse_args()

    if not a.library_root:
        die(2, "CHECK ERROR: --library-root not given and HARNESS_LIBRARY_ROOT unset")
    lib = os.path.realpath(os.path.expanduser(a.library_root))
    if not os.path.isdir(lib):
        die(2, f"CHECK ERROR: library root not a directory: {lib}")
    try:
        payload = json.load(open(a.input))
    except (OSError, json.JSONDecodeError) as e:
        die(2, f"CHECK ERROR: cannot parse --input: {e}")
    requirements = payload.get("requirements", payload if isinstance(payload, list) else [])
    if not requirements:
        die(2, "CHECK ERROR: input carries no requirements")

    records = load_records(a.output)
    fails = check(requirements, records, lib)

    rated = len({r.get("req_id") for r in records})
    print(f"RATE CHECK  requirements: {len(requirements)}  rated: {rated}  "
          f"violations: {len(fails)}")
    if fails:
        print("FAILED:")
        for rid, rule, reason in fails:
            print(f"- {rid} [{rule}]: {reason}")
    if a.report:
        json.dump({"requirements": len(requirements), "rated": rated,
                   "failures": [{"req_id": r, "rule": k, "reason": m} for r, k, m in fails]},
                  open(a.report, "w"), indent=2)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
