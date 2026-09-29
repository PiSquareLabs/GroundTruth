"""Impact report: facts are computed from stored data; the LLM only rephrases those facts."""
from __future__ import annotations

import hashlib
import html
import json
import re
from collections import Counter

from gt import ai_provider, config, db, media

ALL = "all"

PROMPT = """You write short impact summaries for an NGO field-evidence report.
Use ONLY the facts in the JSON below. Rules:
- Do not invent numbers, places, dates, outcomes, beneficiaries or quantities. Only use counts that appear in the facts.
- Cite asset ids in square brackets, e.g. [drain-a-img-01], for every specific claim.
- When describing before/after pairs, say "visible difference between confirmed paired images".
  Never claim verified environmental improvement or impact.
- Never describe anything as evidence of real-world change. Do not discuss whether images are real, synthetic,
  AI-generated or edited, or whether locations/dates are fictional (a fixed disclaimer is added separately).
- Do not restate or mention these rules.
- 100-150 words total (hard limit), plain prose, 2 short paragraphs, no headings, no bullet lists.

FACTS:
{facts}
"""

PROVENANCE_WORDS = ("synthetic", "ai-generated", "generated", "edited", "fictional", "illustrat")


def disclaimer() -> str | None:
    """Plain-text dataset note (seed/dataset.json) used as the report's fixed opening."""
    note = db.get_meta("dataset_note")
    return note.replace("**", "") if note else None


def with_disclaimer(text: str, note: str | None) -> str:
    """Prepend the fixed dataset note ourselves (deterministic wording) and drop any model-written variant."""
    if not note:
        return text
    paras = [p for p in text.strip().split("\n") if p.strip()]
    if paras:
        first, _, rest = paras[0].partition(". ")
        if any(w in first.lower() for w in PROVENANCE_WORDS):
            paras[0] = rest
    return note + "\n\n" + "\n\n".join(p for p in paras if p.strip())


def facts(project_id: str = ALL) -> dict:
    assets = db.assets(None if project_id == ALL else project_id)
    by_id = {a["id"]: a for a in assets}
    pairs = [p for p in db.pairs("confirmed") if p["before_id"] in by_id and p["after_id"] in by_id]
    dates = sorted(a["captured_at"][:10] for a in assets if a.get("captured_at"))
    projects = {}
    for a in assets:
        pr = projects.setdefault(a["project_id"], {"name": a.get("project_name"), "images": 0,
                                                   "activities": Counter(), "signals": Counter()})
        pr["images"] += 1
        if a.get("activity_type"):
            pr["activities"][a["activity_type"]] += 1
        pr["signals"].update(a.get("signals") or [])
    return {
        "scope": project_id,
        "synthetic": any(a.get("synthetic") for a in assets),
        "image_count": len(assets),
        "date_range": [dates[0], dates[-1]] if dates else None,
        "projects": {k: {**v, "activities": dict(v["activities"]), "signals": dict(v["signals"])}
                     for k, v in projects.items()},
        "confirmed_pairs": [
            {
                "before": {"id": p["before_id"], "date": (by_id[p["before_id"]].get("captured_at") or "")[:10],
                           "caption": by_id[p["before_id"]].get("caption"), "signals": by_id[p["before_id"]].get("signals")},
                "after": {"id": p["after_id"], "date": (by_id[p["after_id"]].get("captured_at") or "")[:10],
                          "caption": by_id[p["after_id"]].get("caption"), "signals": by_id[p["after_id"]].get("signals")},
            }
            for p in pairs
        ],
        "images": [{"id": a["id"], "date": (a.get("captured_at") or "")[:10], "caption": a.get("caption")}
                   for a in assets if a.get("caption")],
    }


def facts_hash(f: dict) -> str:
    return hashlib.sha256(json.dumps(f, sort_keys=True).encode()).hexdigest()[:12]


def template_summary(f: dict) -> str:
    """Deterministic, non-AI summary used when no cached or live AI summary is available."""
    if not f["image_count"]:
        return "No evidence in this scope yet."
    names = ", ".join(p["name"] for p in f["projects"].values())
    dr = f"between {f['date_range'][0]} and {f['date_range'][1]}" if f["date_range"] else "on unrecorded dates"
    s = (disclaimer() + " ") if disclaimer() else ""
    s += f"This report covers {f['image_count']} field images from {names}, captured {dr}. "
    n = len(f["confirmed_pairs"])
    s += (f"{n} before/after pair(s) were confirmed by a reviewer and show a visible difference between "
          f"confirmed paired images." if n else "No before/after pairs have been confirmed yet.")
    return s


def cited_ids(text: str) -> set[str]:
    """Asset ids cited in [brackets] (a bracket may hold several, comma-separated)."""
    return {i.strip() for grp in re.findall(r"\[([^\]]+)\]", text or "") for i in grp.split(",") if i.strip()}


def unknown_citations(text: str, known: set[str]) -> list[str]:
    return sorted(cited_ids(text) - known)


def generate_summary(project_id: str = ALL, attempts: int = 3) -> dict:
    """Generate a grounded summary; regenerate if it cites asset ids that don't exist."""
    known = {a["id"] for a in db.assets(None if project_id == ALL else project_id)}
    for _ in range(attempts):
        s = _generate_once(project_id)
        s["citation_issues"] = unknown_citations(s["text"], known)
        if not s["citation_issues"]:
            break
    return s


def _generate_once(project_id: str = ALL) -> dict:
    f = facts(project_id)
    text, used = ai_provider.generate_text(PROMPT.format(facts=json.dumps(f, indent=1)))
    return {"scope": project_id, "text": with_disclaimer(text, disclaimer()), "model": ai_provider.model_name(used),
            "generated_at": db.now_iso(), "facts_hash": facts_hash(f)}


def cached_summary(project_id: str = ALL) -> dict | None:
    """Cached summaries are stored per scope in the seed ('report': {scope: {...}})."""
    raw = db.get_meta("report")
    if not raw:
        return None
    rep = json.loads(raw)
    if "text" in rep:  # single-scope legacy format
        rep = {rep.get("scope", ALL): rep}
    return rep.get(project_id)


def save_summary(summary: dict) -> None:
    raw = db.get_meta("report")
    rep = json.loads(raw) if raw else {}
    rep[summary["scope"]] = summary
    db.set_meta("report", json.dumps(rep))


def evidence_rows(assets: list[dict]) -> list[dict]:
    rows = []
    for a in assets:
        rows.append({
            "asset_id": a["id"],
            "public_id": a.get("public_id") or "(local only)",
            "captured": (a.get("captured_at") or "missing")[:19],
            "original": media.original_url(a) or "",
            "transformations": " | ".join(sorted({t["transformation"] for t in db.transforms(a["id"])})) or "none yet",
        })
    return rows


def to_html(project_label: str, f: dict, summary: dict, summary_is_ai: bool, assets: list[dict]) -> str:
    """Self-contained, print-friendly HTML report (images are Cloudinary URLs)."""
    e = html.escape
    by_id = {a["id"]: a for a in assets}
    pairs_html = ""
    for p in f["confirmed_pairs"]:
        b, a = by_id[p["before"]["id"]], by_id[p["after"]["id"]]
        blur = bool(b.get("people_present") or a.get("people_present"))
        pairs_html += f"""
        <div class="pair">
          <figure><img src="{e(media.url_for(b, 'report', blur) or '')}"><figcaption>Before · {e(b['id'])} · {e(p['before']['date'])}</figcaption></figure>
          <figure><img src="{e(media.url_for(a, 'report', blur) or '')}"><figcaption>After · {e(a['id'])} · {e(p['after']['date'])}</figcaption></figure>
        </div>"""
    timeline = "".join(
        f"<li><b>{e(i['date'] or 'undated')}</b> · {e(i['id'])} — {e(i['caption'] or '')}</li>"
        for i in sorted(f["images"], key=lambda x: x["date"] or "9999"))
    ev = "".join(
        f"<tr><td>{e(r['asset_id'])}</td><td>{e(r['public_id'])}</td><td>{e(r['captured'])}</td>"
        f"<td><a href='{e(r['original'])}'>original</a></td><td><code>{e(r['transformations'])}</code></td></tr>"
        for r in evidence_rows(assets))
    label = (f"AI-suggested summary · {e(summary.get('model', ''))} · generated {e(summary.get('generated_at', ''))}"
             if summary_is_ai else "Template summary (no AI)")
    dr = " to ".join(f["date_range"]) if f["date_range"] else "n/a"
    note = disclaimer()
    syn = f"<p class='syn'>🧪 {e(note)}</p>" if note else ""
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Ground Truth report · {e(project_label)}</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:900px;margin:24px auto;padding:0 16px;color:#1b1b1b}}
h1{{color:#2E7D32}} .label{{font-size:12px;color:#666}} .note{{background:#f3f6f3;padding:8px 12px;border-radius:6px;font-size:13px}}
.pair{{display:flex;gap:12px;margin:12px 0;page-break-inside:avoid}} figure{{margin:0;flex:1}} img{{width:100%;border-radius:4px}}
figcaption{{font-size:12px;color:#555}} table{{border-collapse:collapse;width:100%;font-size:11px}} td,th{{border:1px solid #ddd;padding:4px;text-align:left;vertical-align:top}}
code{{font-size:10px;word-break:break-all}} .syn{{background:#fff3e0;border:2px solid #ef6c00;padding:8px 12px;border-radius:6px;font-weight:600}} @media print{{.noprint{{display:none}} a{{color:inherit}}}}
</style></head><body>
<button class="noprint" onclick="window.print()">Print / save as PDF</button>
<h1>Ground Truth impact report</h1>
<p><b>Scope:</b> {e(project_label)} · <b>Images:</b> {f['image_count']} · <b>Confirmed pairs:</b> {len(f['confirmed_pairs'])} · <b>Dates:</b> {e(dr)}</p>
{syn}<h2>Summary</h2><p class="label">{label}</p>
<div>{"".join(f"<p>{e(par)}</p>" for par in summary['text'].split(chr(10)) if par.strip())}</div>
<p class="note">Before/after pairs show visible difference between confirmed paired images. They do not verify an environmental outcome.
Captions and tags are AI-suggested. Faces are blurred where people may appear.</p>
<h2>Confirmed before/after pairs</h2>{pairs_html or "<p>None confirmed.</p>"}
<h2>Timeline</h2><ul>{timeline}</ul>
<h2>Evidence table</h2>
<table><tr><th>Asset</th><th>Cloudinary public_id</th><th>Captured</th><th>Source</th><th>Transformations</th></tr>{ev}</table>
<p class="label">Generated by Ground Truth · github.com/PiSquareLabs/ground-truth-cloudinary</p>
</body></html>"""
