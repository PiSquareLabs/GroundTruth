"""Build the demo seed: upload seed images to Cloudinary, analyze them once, write seed/analysis.json.

Inputs:
    seed/metadata.csv       filename, project, captured_at, lat, lng, role[before|after|filler|duplicate], synthetic
    seed/images/<filename>  (or seed/<filename>) the image files listed in metadata.csv
    seed/projects.json      optional: nicer names/descriptions per project id
    seed/confirmed_pairs.txt  optional, human-reviewed "before_id after_id" per line

The seed images are SYNTHETIC (computer-generated) and their locations/dates are fictional. metadata.csv is the
source for capture time and GPS (generated images carry no real EXIF).

Usage (needs CLOUDINARY_URL and GEMINI_API_KEY in .env):
    python scripts/seed_cloudinary.py                     # incremental
    python scripts/seed_cloudinary.py --force             # re-analyze everything
    python scripts/seed_cloudinary.py --confirm-by-role   # confirm suggested before->after pairs matching the CSV roles
    python scripts/seed_cloudinary.py --report            # (re)generate cached report summaries
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageOps  # noqa: E402

from gt import analysis, config, exif, media, pairing, seed  # noqa: E402

EXTS = {".jpg", ".jpeg", ".png", ".webp"}  # convert HEIC to JPEG first
ROLES = {"before", "after", "filler", "duplicate"}


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def truthy(s: str | None, default: bool = True) -> bool:
    if s is None or not str(s).strip():
        return default
    return str(s).strip().lower() in ("1", "true", "yes", "y")


def parse_dt(s: str | None) -> str | None:
    s = (s or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).isoformat()
        except ValueError:
            pass
    print(f"  ! unparseable captured_at {s!r}; left empty")
    return None


def parse_float(s: str | None) -> float | None:
    try:
        return float(s) if s and s.strip() else None
    except ValueError:
        return None


def resolve(filename: str) -> Path | None:
    for base in (config.SEED_IMAGES, config.SEED_DIR):
        p = base / filename
        if p.is_file():
            return p
    return None


def ai_bytes(path: Path) -> tuple[bytes, str]:
    """Downscaled JPEG copy for the vision model (the original goes to Cloudinary untouched)."""
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((1600, 1600))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=85)
    return buf.getvalue(), "image/jpeg"


def read_manifest() -> list[dict]:
    path = config.SEED_DIR / "metadata.csv"
    if not path.exists():
        sys.exit(f"Missing {path} (columns: filename, project, captured_at, lat, lng, role, synthetic)")
    with path.open(newline="", encoding="utf-8-sig") as fh:
        rows = [{k.strip().lower(): (v or "").strip() for k, v in r.items() if k} for r in csv.DictReader(fh)]
    out = []
    for r in rows:
        if not r.get("filename"):
            continue
        role = r.get("role", "").lower()
        if role and role not in ROLES:
            print(f"  ! {r['filename']}: unknown role {role!r}")
        out.append({**r, "role": role or None, "project_id": slug(r.get("project") or "unassigned")})
    return out


def update_sources(files: list[str]) -> None:
    """Keep seed/SOURCES.md listing every seed file; never overwrite rows the user filled in."""
    path = config.SEED_DIR / "SOURCES.md"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    missing = [f for f in files if f"| {f} |" not in text]
    if missing:
        with path.open("a", encoding="utf-8") as fh:
            for f in missing:
                fh.write(f"| {f} | _TODO_ | _TODO_ |\n")
        print(f"Added {len(missing)} row(s) to {path.name}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="re-analyze images that already have an analysis")
    ap.add_argument("--report", action="store_true", help="regenerate the cached report summaries")
    ap.add_argument("--skip-ai", action="store_true", help="upload + metadata only")
    ap.add_argument("--confirm-by-role", action="store_true",
                    help="reviewer shortcut: confirm suggested pairs whose CSV roles are before->after in one project")
    args = ap.parse_args()
    sys.stdout.reconfigure(line_buffering=True, encoding="utf-8")

    if not config.cloudinary_ready():
        sys.exit("CLOUDINARY_URL is not set (see .env.example).")
    if not args.skip_ai and not config.ai_ready():
        sys.exit("GEMINI_API_KEY is not set (or pass --skip-ai).")

    manifest = read_manifest()
    named = {}
    pj = config.SEED_DIR / "projects.json"
    if pj.exists():
        named = {p["id"]: p for p in json.loads(pj.read_text(encoding="utf-8"))}
    projects, seen = [], set()
    for r in manifest:
        pid = r["project_id"]
        if pid not in seen:
            seen.add(pid)
            projects.append(named.get(pid) or {
                "id": pid, "name": r.get("project") or pid,
                "description": "Synthetic demo project (computer-generated images, fictional location and dates).",
                "location_name": "Fictional location",
            })

    data = seed.read_seed()
    existing = {a["id"]: a for a in data["assets"]}
    data.update(projects=projects, cloud_name=media.cloud_name(), synthetic=True)
    assets = []

    for r in manifest:
        f = resolve(r["filename"])
        if f is None or f.suffix.lower() not in EXTS:
            print(f"  ! skipping {r['filename']}: file not found or unsupported type")
            continue
        pid = r["project_id"]
        aid = f"{pid}-{slug(f.stem)}"
        rec = existing.get(aid, {})
        if not rec.get("public_id"):
            res = media.upload(str(f), public_id=slug(f.stem), project_id=pid)
            rec = {
                "id": aid, "public_id": res["public_id"], "url": res["secure_url"],
                "width": res.get("width"), "height": res.get("height"), "bytes": res.get("bytes"),
                "format": res.get("format"), "uploaded_at": res.get("created_at"),
            }
            print(f"  uploaded {aid} -> {res['public_id']}")
        # metadata.csv is authoritative and re-applied on every run (edits to the CSV take effect)
        meta = exif.extract(f)
        rec.update(
            project_id=pid, filename=r["filename"], source="seed",
            captured_at=parse_dt(r.get("captured_at")) or meta["captured_at"],
            lat=parse_float(r.get("lat")) if r.get("lat") else meta["lat"],
            lng=parse_float(r.get("lng")) if r.get("lng") else meta["lng"],
            exif=meta["exif"], metadata_source="seed/metadata.csv (fictional)",
            role=r["role"], synthetic=truthy(r.get("synthetic"), default=True),
        )
        if not rec["synthetic"]:
            print(f"  ! {aid}: synthetic=false in metadata.csv; seed images are expected to be synthetic")
        an = rec.get("analysis")
        if not args.skip_ai and (args.force or not an or an.get("needs_review")):
            b, mime = ai_bytes(f)
            try:
                rec["analysis"] = analysis.analyze(b, mime)
            except Exception as e:  # keep going; the image is flagged instead
                rec["analysis"] = {"needs_review": True, "raw_output": f"ERROR: {e}", "tags": [], "signals": []}
            flag = " (needs review)" if rec["analysis"].get("needs_review") else ""
            print(f"  analyzed {aid}: {rec['analysis'].get('caption')}{flag}")
        assets.append(rec)
        # checkpoint after each image so an interrupted run resumes without redoing work
        seed.write_seed({**data, "assets": assets + [a for a in data["assets"] if a["id"] not in {x["id"] for x in assets}]})

    data["assets"] = assets
    update_sources([r["filename"] for r in manifest])

    # Pair suggestions. Confirmation is a human decision: confirmed_pairs.txt, or --confirm-by-role.
    flat = [{**a, **(a.get("analysis") or {})} for a in assets]
    ids = {a["id"]: a for a in flat}
    by_key = {(s["before_id"], s["after_id"]): s for s in pairing.suggest(flat)}
    confirmed = set()
    cf = config.SEED_DIR / "confirmed_pairs.txt"
    if cf.exists():
        for line in cf.read_text(encoding="utf-8").splitlines():
            parts = line.split("#")[0].split()
            if len(parts) == 2 and parts[0] in ids and parts[1] in ids:
                confirmed.add(tuple(parts))
    if args.confirm_by_role:
        confirmed |= {k for k in by_key if ids[k[0]].get("role") == "before" and ids[k[1]].get("role") == "after"
                      and ids[k[0]]["project_id"] == ids[k[1]]["project_id"]}
    for b, a in confirmed:  # a confirmed pair may score below the suggestion threshold
        if (b, a) not in by_key:
            s, bd = pairing.score_pair(ids[b], ids[a])
            by_key[(b, a)] = {"before_id": b, "after_id": a, "score": s, "breakdown": bd}
    data["pairs"] = [{**s, "status": "confirmed" if k in confirmed else "suggested"} for k, s in by_key.items()]
    print(f"{len(data['pairs'])} pairs ({len(confirmed)} confirmed):")
    for pr in sorted(data["pairs"], key=lambda x: -x["score"]):
        roles = f"{ids[pr['before_id']].get('role')}->{ids[pr['after_id']].get('role')}"
        print(f"  {pr['before_id']} {pr['after_id']}  {pr['score']:.2f}  [{roles}]  "
              f"{'CONFIRMED' if pr['status'] == 'confirmed' else ''}")

    seed.write_seed(data)
    print(f"Wrote {config.SEED_FILE}")

    if args.report:
        from gt import report  # imported lazily: needs the DB built from the new seed

        config.DEMO_MODE = True
        seed.ensure_loaded()
        scopes = [report.ALL] + [p["id"] for p in projects]
        data["report"] = {sc: report.generate_summary(sc) for sc in scopes}
        seed.write_seed(data)
        print(f"Cached report summaries for: {', '.join(scopes)}")


if __name__ == "__main__":
    main()
