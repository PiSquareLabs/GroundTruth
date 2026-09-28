"""Build the demo seed: upload seed images to Cloudinary, analyze them once, write seed/analysis.json.

Layout expected:
    seed/projects.json                 [{"id", "name", "description", "location_name"}]
    seed/images/<project_id>/*.jpg     photos you own, one folder per project
    seed/confirmed_pairs.txt           optional, human-reviewed "before_id after_id" per line

Usage (needs CLOUDINARY_URL and GEMINI_API_KEY in .env):
    python scripts/seed_cloudinary.py            # incremental: skips already processed images
    python scripts/seed_cloudinary.py --force    # re-analyze everything
    python scripts/seed_cloudinary.py --report   # also (re)generate the cached report summary
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageOps  # noqa: E402

from gt import analysis, config, exif, media, pairing, seed  # noqa: E402

EXTS = {".jpg", ".jpeg", ".png", ".webp"}  # convert HEIC to JPEG first


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def ai_bytes(path: Path) -> tuple[bytes, str]:
    """Downscaled JPEG copy for the vision model (the original goes to Cloudinary untouched)."""
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((1600, 1600))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=85)
    return buf.getvalue(), "image/jpeg"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="re-analyze images that already have an analysis")
    ap.add_argument("--report", action="store_true", help="regenerate the cached report summary")
    ap.add_argument("--skip-ai", action="store_true", help="upload + EXIF only")
    args = ap.parse_args()

    if not config.cloudinary_ready():
        sys.exit("CLOUDINARY_URL is not set (see .env.example).")
    if not args.skip_ai and not config.ai_ready():
        sys.exit("GEMINI_API_KEY is not set (or pass --skip-ai).")

    projects_file = config.SEED_DIR / "projects.json"
    if not projects_file.exists():
        sys.exit(f"Missing {projects_file}")
    projects = json.loads(projects_file.read_text(encoding="utf-8"))

    data = seed.read_seed()
    existing = {a["id"]: a for a in data["assets"]}
    data["projects"] = projects
    data["cloud_name"] = media.cloud_name()
    assets = []

    for p in projects:
        folder = config.SEED_IMAGES / p["id"]
        files = sorted(f for f in folder.glob("*") if f.suffix.lower() in EXTS) if folder.exists() else []
        print(f"[{p['id']}] {len(files)} images")
        for f in files:
            aid = f"{p['id']}-{slug(f.stem)}"
            rec = existing.get(aid, {})
            if not rec.get("public_id"):
                meta = exif.extract(f)
                res = media.upload(str(f), public_id=slug(f.stem), project_id=p["id"])
                rec = {
                    "id": aid, "project_id": p["id"], "filename": f"{p['id']}/{f.name}",
                    "public_id": res["public_id"], "url": res["secure_url"],
                    "width": res.get("width"), "height": res.get("height"), "bytes": res.get("bytes"),
                    "format": res.get("format"), "uploaded_at": res.get("created_at"),
                    "captured_at": meta["captured_at"], "lat": meta["lat"], "lng": meta["lng"],
                    "exif": meta["exif"], "source": "seed",
                }
                print(f"  uploaded {aid} -> {res['public_id']}")
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

    data["assets"] = assets

    # Pair suggestions; human-confirmed pairs come from seed/confirmed_pairs.txt
    flat = [{**a, **(a.get("analysis") or {})} for a in assets]
    suggestions = pairing.suggest(flat)
    confirmed_file = config.SEED_DIR / "confirmed_pairs.txt"
    confirmed = set()
    if confirmed_file.exists():
        for line in confirmed_file.read_text(encoding="utf-8").splitlines():
            parts = line.split("#")[0].split()
            if len(parts) == 2:
                confirmed.add(tuple(parts))
    by_key = {(s["before_id"], s["after_id"]): s for s in suggestions}
    ids = {a["id"]: a for a in flat}
    for b, a in confirmed:  # a confirmed pair may score below the suggestion threshold
        if (b, a) not in by_key and b in ids and a in ids:
            s, bd = pairing.score_pair(ids[b], ids[a])
            by_key[(b, a)] = {"before_id": b, "after_id": a, "score": s, "breakdown": bd}
    data["pairs"] = [
        {**s, "status": "confirmed" if k in confirmed else "suggested"} for k, s in by_key.items()
    ]
    print(f"{len(data['pairs'])} pairs ({len(confirmed)} confirmed)")

    seed.write_seed(data)
    print(f"Wrote {config.SEED_FILE}")

    if args.report:
        from gt import report  # imported lazily: needs the DB built from the new seed

        config.DEMO_MODE = True
        seed.ensure_loaded()
        data["report"] = report.generate_summary()
        seed.write_seed(data)
        print("Cached report summary.")


if __name__ == "__main__":
    main()
