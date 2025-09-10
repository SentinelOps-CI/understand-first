import os, json, time, datetime
from ucli.config import load_config

EVENTS = "metrics/events.jsonl"


def record(event: str, extra=None):
    cfg = load_config()
    if not (cfg.get("metrics", {}) or {}).get("enabled", False):
        return
    os.makedirs(os.path.dirname(EVENTS), exist_ok=True)
    with open(EVENTS, "a", encoding="utf-8") as f:
        f.write(
            json.dumps({"ts": int(time.time()), "event": event, "extra": extra or {}})
            + "\n"
        )


def weekly_report(outfile="docs/ttu.md"):
    if not os.path.exists(EVENTS):
        os.makedirs(os.path.dirname(outfile), exist_ok=True)
        open(outfile, "w", encoding="utf-8").write("# TTU\nNo data yet.\n")
        return outfile
    rows = []
    with open(EVENTS, "r", encoding="utf-8") as f:
        for line in f:
            try:
                rows.append(json.loads(line))
            except:
                pass
    # naive: compute deltas between first map_open -> tour_run -> fixture_pass per day
    days = {}
    for r in rows:
        day = datetime.datetime.utcfromtimestamp(r["ts"]).strftime("%Y-%m-%d")
        days.setdefault(day, {}).setdefault(r["event"], []).append(r["ts"])
    md = ["# Time to Understanding (TTU)", ""]
    for d, ev in sorted(days.items()):
        map_t = min(ev.get("map_open", []), default=None)
        tour_t = min(ev.get("tour_run", []), default=None)
        fix_t = min(ev.get("fixture_pass", []), default=None)
        parts = [f"**{d}**:"]
        if map_t and tour_t:
            parts.append(f"map→tour: {tour_t - map_t}s")
        if tour_t and fix_t:
            parts.append(f"tour→fixture: {fix_t - tour_t}s")
        md.append("- " + " ".join(parts))
    os.makedirs(os.path.dirname(outfile), exist_ok=True)
    with open(outfile, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    return outfile
