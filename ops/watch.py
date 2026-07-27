#!/usr/bin/env python3
"""ops/watch.py — deterministic run-health engine for the Ops Watcher (Phase 4 attention layer).

Reads:
  runs/scheduled-tasks-snapshot.json  — verbatim output of list_scheduled_tasks, written by the watcher agent
  runs/digest.jsonl                   — Lane-2 queue (ESCALATION-POLICY.md Mechanics)

Writes:
  runs/ops-status.json                — machine-readable health snapshot
  mission-control.html                — brand-styled dashboard (gitignored, generated)

Prints a compact summary to stdout for the watcher agent. Exit 0 always (the agent
decides escalation from the summary; a crash here is itself a watcher failure).

No third-party dependencies. Cron evaluated in local time (same Mac that fires the tasks).
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = ROOT / "runs" / "scheduled-tasks-snapshot.json"
DIGEST = ROOT / "runs" / "digest.jsonl"
STATUS_OUT = ROOT / "runs" / "ops-status.json"
HTML_OUT = ROOT / "mission-control.html"

RUN_GRACE = timedelta(minutes=45)   # allowance past fire+jitter before a run counts as missed
LATE_SLACK = timedelta(seconds=120)  # lastRunAt may precede the matched fire minute slightly

# ---------------------------------------------------------------- cron matching

def _field_matches(field: str, value: int, lo: int, hi: int) -> bool:
    for part in field.split(","):
        step = 1
        if "/" in part:
            part, step_s = part.split("/", 1)
            step = int(step_s)
        if part == "*":
            rng = range(lo, hi + 1)
        elif "-" in part:
            a, b = part.split("-", 1)
            rng = range(int(a), int(b) + 1)
        else:
            rng = range(int(part), int(part) + 1)
        if value in rng and (value - rng.start) % step == 0:
            return True
    return False


def cron_matches(expr: str, dt: datetime) -> bool:
    minute, hour, dom, mon, dow = expr.split()
    cron_dow = (dt.weekday() + 1) % 7  # cron: 0 = Sunday
    return (
        _field_matches(minute, dt.minute, 0, 59)
        and _field_matches(hour, dt.hour, 0, 23)
        and _field_matches(dom, dt.day, 1, 31)
        and _field_matches(mon, dt.month, 1, 12)
        and _field_matches(dow, cron_dow, 0, 6)
    )


def prev_fire(expr: str, now: datetime, lookback_days: int = 9):
    """Most recent scheduled fire time at or before `now` (local), else None."""
    dt = now.replace(second=0, microsecond=0)
    for _ in range(lookback_days * 1440):
        if cron_matches(expr, dt):
            return dt
        dt -= timedelta(minutes=1)
    return None

# ---------------------------------------------------------------- helpers

def parse_iso(s):
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone()


def fmt(dt, now):
    if dt is None:
        return "—"
    d = dt.strftime("%a %-m/%-d %-I:%M %p")
    delta = now - dt
    if timedelta(0) <= delta < timedelta(hours=48):
        hrs = delta.total_seconds() / 3600
        d += f" ({hrs:.0f}h ago)" if hrs >= 1 else f" ({delta.total_seconds()/60:.0f}m ago)"
    return d

# ---------------------------------------------------------------- health

def assess(task: dict, now: datetime) -> dict:
    out = {
        "taskId": task["taskId"],
        "description": task.get("description", ""),
        "schedule": task.get("schedule", ""),
        "enabled": task.get("enabled", False),
        "lastRunAt": task.get("lastRunAt"),
        "nextRunAt": task.get("nextRunAt"),
        "oneTime": "fireAt" in task,
    }
    last = parse_iso(task.get("lastRunAt"))
    jitter = timedelta(seconds=task.get("jitterSeconds", 0) or 0)

    if out["oneTime"]:
        fire = parse_iso(task.get("fireAt"))
        if last is not None:
            out["status"], out["detail"] = "done", "one-time task, completed"
        elif not task.get("enabled"):
            out["status"], out["detail"] = "off", "one-time task, disabled without running"
        elif fire and fire < now - RUN_GRACE:
            out["status"], out["detail"] = "missed", f"one-time fire {fmt(fire, now)} passed with no run"
        else:
            out["status"], out["detail"] = "scheduled", f"fires {fmt(fire, now)}"
        return out

    expr = task.get("cronExpression")
    if not task.get("enabled"):
        out["status"] = "off"
        out["detail"] = "recurring task is DISABLED — verify this is intentional"
        return out
    if not expr:
        out["status"], out["detail"] = "note", "enabled but no cronExpression"
        return out

    expected = prev_fire(expr, now)
    out["expectedLast"] = expected.isoformat() if expected else None
    if expected is None:
        out["status"], out["detail"] = "ok", "no fire due in lookback window"
    elif last is not None and last >= expected - LATE_SLACK:
        out["status"], out["detail"] = "ok", f"ran {fmt(last, now)}"
    elif now <= expected + jitter + RUN_GRACE:
        out["status"] = "pending"
        out["detail"] = f"fire window open (due {expected.strftime('%-I:%M %p')}, jitter+grace not elapsed)"
    else:
        out["status"] = "missed"
        out["detail"] = f"expected {fmt(expected, now)}, last ran {fmt(last, now)}"
    return out


def read_digest(now: datetime):
    items, counts = [], {"new": 0, "sent": 0, "expiring": 0, "stale": 0}
    if DIGEST.exists():
        for line in DIGEST.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            st = row.get("status", "new")
            counts[st] = counts.get(st, 0) + 1
            ts = parse_iso(row.get("ts"))
            age = (now - ts).days if ts else None
            if st in ("new", "expiring"):
                items.append({
                    "ts": row.get("ts"), "age_days": age,
                    "severity": row.get("severity", ""), "category": row.get("category", ""),
                    "text": row.get("text", ""), "source": row.get("source", ""), "status": st,
                })
    return items, counts

# ---------------------------------------------------------------- dashboard

BADGE = {
    "ok":        ("#15803D", "#2E9E5B", "OK"),
    "pending":   ("#2B6CB0", "#2B6CB0", "In window"),
    "missed":    ("#B91C1C", "#D64545", "Missed"),
    "off":       ("#B45309", "#E0A33E", "Disabled"),
    "note":      ("#B45309", "#E0A33E", "Note"),
    "done":      ("#4D5757", "#97A3A3", "Done"),
    "scheduled": ("#2B6CB0", "#2B6CB0", "Scheduled"),
}


def badge(status):
    text, dot, label = BADGE.get(status, BADGE["note"])
    return (f'<span class="badge" style="--dot:{dot};--btext:{text}">'
            f'<span class="dot"></span>{label}</span>')


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def render_html(assessed, digest_items, digest_counts, now):
    active = [t for t in assessed if not t["oneTime"] and t["enabled"]]
    retired = [t for t in assessed if t not in active]
    n_ok = sum(1 for t in active if t["status"] == "ok")
    n_bad = sum(1 for t in active if t["status"] == "missed")
    n_pend = sum(1 for t in active if t["status"] == "pending")
    n_queue = digest_counts.get("new", 0) + digest_counts.get("expiring", 0)

    def task_rows(tasks):
        rows = []
        for t in sorted(tasks, key=lambda x: ({"missed": 0, "pending": 1, "off": 2, "note": 2}.get(x["status"], 3), x["taskId"])):
            last = fmt(parse_iso(t.get("lastRunAt")), now)
            nxt = fmt(parse_iso(t.get("nextRunAt")), now)
            rows.append(
                f'<tr><td>{badge(t["status"])}<div class="tdetail">{esc(t["detail"])}</div></td>'
                f'<td class="tname"><strong>{esc(t["taskId"])}</strong>'
                f'<div class="tdesc">{esc(t["description"])}</div></td>'
                f'<td class="sched">{esc(t["schedule"])}</td>'
                f'<td class="mono">{esc(last)}</td>'
                f'<td class="mono">{esc(nxt)}</td></tr>'
            )
        return "\n".join(rows)

    attention = [t for t in active if t["status"] in ("missed", "off", "note")]
    attention_html = ""
    if attention or any(i["status"] == "expiring" or (i["age_days"] or 0) >= 12 for i in digest_items):
        lines = [f'<li><strong>{esc(t["taskId"])}</strong> — {esc(t["detail"])}</li>' for t in attention]
        lines += [f'<li><strong>digest item aging</strong> — {esc(i["text"])[:140]} (day {i["age_days"]})</li>'
                  for i in digest_items if i["status"] == "expiring" or (i["age_days"] or 0) >= 12]
        attention_html = ('<section><h2>Needs attention</h2><ul class="attn">' + "\n".join(lines) + "</ul></section>")

    digest_rows = "\n".join(
        f'<tr><td class="mono">{esc((i["ts"] or "")[:10])}</td>'
        f'<td class="mono">{i["age_days"]}d</td><td>{esc(i["severity"])}</td>'
        f'<td>{esc(i["category"])}</td><td>{esc(i["text"])}</td></tr>'
        for i in sorted(digest_items, key=lambda x: x["ts"] or "")
    ) or '<tr><td colspan="5" class="empty">Queue is clear.</td></tr>'

    stamp = now.strftime("%A %B %-d, %Y · %-I:%M %p %Z")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mission Control — Ed Matibag</title>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,900&family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root {{ --bg:#FFFFFF; --surface:#FFFFFF; --raised:#F7F9F9; --border:#DDE3E3; --text:#0B0F0F;
  --muted:#6B7777; --brand:#2C7A6B; --brand-strong:#1F6457; --accent:#2B4C7E; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg:#0F1414; --surface:#161D1C; --raised:#1E2726; --border:#2A3433; --text:#ECF1F0;
    --muted:#97A3A3; --brand:#5BAE9E; --brand-strong:#5BAE9E; --accent:#7FA6D6; }} }}
* {{ box-sizing:border-box; margin:0; }}
body {{ background:var(--bg); color:var(--text); font:400 16px/1.55 Inter,system-ui,sans-serif;
  max-width:1080px; margin:0 auto; padding:32px 24px 64px; }}
h1 {{ font:900 36px/1.15 Fraunces,serif; }}
h2 {{ font:600 22px/1.2 Fraunces,serif; color:var(--accent); margin:40px 0 12px; }}
.sub {{ color:var(--muted); font-size:14px; margin-top:4px; }}
header {{ display:flex; align-items:center; gap:14px; border-bottom:3px solid var(--brand); padding-bottom:18px; }}
.tile {{ width:44px; height:44px; border-radius:10px; flex:none;
  background:linear-gradient(135deg,#2C7A6B,#2B4C7E); display:flex; align-items:center; justify-content:center;
  color:#fff; font:600 20px Fraunces,serif; }}
.tiles {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:12px; margin-top:24px; }}
.stat {{ background:var(--raised); border:1px solid var(--border); border-radius:12px; padding:14px 16px; }}
.stat .n {{ font:600 32px/1.1 "IBM Plex Mono",monospace; }}
.stat .l {{ color:var(--muted); font-size:13px; margin-top:2px; }}
.tablewrap {{ overflow-x:auto; border:1px solid var(--border); border-radius:12px; }}
table {{ border-collapse:collapse; width:100%; font-size:14px; background:var(--surface); }}
th {{ text-align:left; font:600 11px/1.2 Inter; letter-spacing:.08em; text-transform:uppercase;
  color:var(--muted); padding:10px 12px; border-bottom:1px solid var(--border); }}
td {{ padding:10px 12px; border-bottom:1px solid var(--border); vertical-align:top; }}
tr:last-child td {{ border-bottom:none; }}
.mono {{ font-family:"IBM Plex Mono",monospace; font-size:13px; font-variant-numeric:tabular-nums; white-space:nowrap; }}
.tname strong {{ font-weight:600; white-space:nowrap; }}
.sched {{ min-width:150px; }}
.tdesc,.tdetail {{ color:var(--muted); font-size:12.5px; margin-top:2px; max-width:340px; min-width:180px;
  display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }}
.badge {{ display:inline-flex; align-items:center; gap:6px; font:600 12.5px Inter; color:var(--btext); white-space:nowrap; }}
.badge .dot {{ width:8px; height:8px; border-radius:50%; background:var(--dot); flex:none; }}
@media (prefers-color-scheme: dark) {{ .badge {{ color:var(--dot); }} }}
.attn {{ background:var(--raised); border:1px solid var(--border); border-left:4px solid #D64545;
  border-radius:8px; padding:14px 18px 14px 34px; }}
.attn li {{ margin:4px 0; }}
.empty {{ color:var(--muted); text-align:center; padding:18px; }}
details {{ margin-top:10px; }} summary {{ cursor:pointer; color:var(--muted); font-size:14px; }}
footer {{ margin-top:48px; color:var(--muted); font-size:12.5px; border-top:1px solid var(--border); padding-top:14px; }}
</style></head><body>
<header>
  <div class="tile">EM</div>
  <div><h1>Mission Control</h1>
  <div class="sub">Routines &amp; attention queue · generated {esc(stamp)}</div></div>
</header>

<div class="tiles">
  <div class="stat"><div class="n" style="color:{'#15803D' if n_bad==0 else 'var(--text)'}">{n_ok}/{len(active)}</div><div class="l">routines healthy</div></div>
  <div class="stat"><div class="n" style="color:{'#B91C1C' if n_bad else 'var(--text)'}">{n_bad}</div><div class="l">missed / failed</div></div>
  <div class="stat"><div class="n">{n_pend}</div><div class="l">in fire window</div></div>
  <div class="stat"><div class="n">{n_queue}</div><div class="l">open digest items</div></div>
</div>

{attention_html}

<section><h2>Routines</h2>
<div class="tablewrap"><table>
<thead><tr><th>Status</th><th>Routine</th><th>Schedule</th><th>Last run</th><th>Next run</th></tr></thead>
<tbody>{task_rows(active)}</tbody></table></div></section>

<section><h2>Digest queue (Lane 2)</h2>
<div class="tablewrap"><table>
<thead><tr><th>Filed</th><th>Age</th><th>Severity</th><th>Category</th><th>Item</th></tr></thead>
<tbody>{digest_rows}</tbody></table></div>
<div class="sub">Delivered nightly by <strong>evening-digest</strong> · expiring at day 12 · stale at day 14 (per ESCALATION-POLICY.md)</div></section>

<section><details><summary>One-time &amp; retired tasks ({len(retired)})</summary>
<div class="tablewrap" style="margin-top:10px"><table>
<thead><tr><th>Status</th><th>Task</th><th>Schedule</th><th>Last run</th><th>Next run</th></tr></thead>
<tbody>{task_rows(retired)}</tbody></table></div></details></section>

<footer>Ops Watcher · AI-orchestration-layer Phase 4 attention layer · source of truth:
runs/ops-status.json &amp; runs/digest.jsonl · this page is generated — do not edit.</footer>
</body></html>
"""

# ---------------------------------------------------------------- main

def main():
    now = datetime.now().astimezone()
    if not SNAPSHOT.exists():
        print(f"ERROR: snapshot not found at {SNAPSHOT} — write list_scheduled_tasks output there first.")
        return
    tasks = json.loads(SNAPSHOT.read_text())
    assessed = [assess(t, now) for t in tasks]
    digest_items, digest_counts = read_digest(now)

    active = [t for t in assessed if not t["oneTime"] and t["enabled"]]
    missed = [t for t in active if t["status"] == "missed"]
    flags = [t for t in assessed if t["status"] in ("off", "note") and not t["oneTime"]]
    aging = [i for i in digest_items if i["status"] == "expiring" or (i["age_days"] or 0) >= 12]

    STATUS_OUT.write_text(json.dumps({
        "generated_at": now.isoformat(),
        "tasks": assessed,
        "digest": {"counts": digest_counts, "open_items": digest_items},
        "summary": {"active": len(active), "ok": sum(1 for t in active if t["status"] == "ok"),
                    "pending": sum(1 for t in active if t["status"] == "pending"),
                    "missed": len(missed), "flags": len(flags), "digest_open": len(digest_items)},
    }, indent=2))
    HTML_OUT.write_text(render_html(assessed, digest_items, digest_counts, now))

    print(f"OPS-WATCH {now.strftime('%Y-%m-%d %H:%M %Z')}")
    print(f"ROUTINES: {len(active)} active — "
          f"{sum(1 for t in active if t['status']=='ok')} OK, "
          f"{sum(1 for t in active if t['status']=='pending')} in-window, {len(missed)} MISSED")
    for t in missed:
        print(f"  [MISSED] {t['taskId']} — {t['detail']}")
    for t in flags:
        print(f"  [FLAG] {t['taskId']} — {t['detail']}")
    print(f"DIGEST: {digest_counts.get('new',0)} new, {digest_counts.get('expiring',0)} expiring, "
          f"{digest_counts.get('stale',0)} stale")
    for i in aging:
        print(f"  [AGING] day {i['age_days']}: {i['text'][:110]}")
    print(f"WROTE: {STATUS_OUT.relative_to(ROOT)} + {HTML_OUT.name}")
    print(f"ESCALATE-CANDIDATE: {'YES' if missed else 'no'}"
          + (f" — {len(missed)} missed run(s); investigate cause, then Slack DM Ed per severity gate" if missed else ""))


if __name__ == "__main__":
    sys.exit(main())
