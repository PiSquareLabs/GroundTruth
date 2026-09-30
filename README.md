# 🌱 Ground Truth

**AI-organized before/after field evidence and traceable impact reports for NGOs, built on Cloudinary.**

**Live Demo:** [https://ground-truth-cloudinary-n3i564mqhcg87ltuqrqprw.streamlit.app](https://ground-truth-cloudinary-n3i564mqhcg87ltuqrqprw.streamlit.app) · **Demo video:** [docs/demo/ground-truth-demo.mp4](docs/demo/ground-truth-demo.mp4) ([script](docs/demo/DEMO_SCRIPT.md))

> 🧪 **About the demo dataset.** The **before** photos are real photos; the **after** images are **AI-generated or edited**
> illustrations of the intended repair. Locations (Kochi, Kerala) and dates are **fictional**, assigned for the demo.
> Nothing in the demo is evidence of a real-world repair. See [Demo dataset](#demo-dataset).

Built for **Code Cubicle 6.0** (Cloudinary problem statement).
Repo: [github.com/PiSquareLabs/ground-truth-cloudinary](https://github.com/PiSquareLabs/ground-truth-cloudinary)

---

## Problem

NGOs and volunteers take thousands of phone photos of civic and environmental work: drain cleaning, tree planting, road repair, waste clearing. They end up scattered across phones and chat groups with no structure. When a funder or city official asks what changed, someone has to hunt for "before" and "after" shots by hand. The reports that come out are hard to verify and easy to exaggerate.

## Solution

Ground Truth turns a pile of field photos into organized, searchable, **traceable** evidence:

1. **Organize.** Every photo is stored on Cloudinary, grouped by project, and placed in time and space from its EXIF capture date and GPS.
2. **Understand.** A vision model writes a factual caption, activity type, visible *signals* (standing water, litter, bare soil, saplings, fresh asphalt…) and tags, all labelled **AI-suggested**.
3. **Search by meaning.** The Evidence library's search box runs semantic search over the caption and tag embeddings, and each result explains *why it matched*. The app is laid out as four steps (Collect → Explore → Review → Share) plus a Trace page, with a built-in tour and a "How this page works" help popover on every page.
4. **Compare.** The app suggests before/after pairs using location, visual similarity and time. **A person confirms or rejects each one.** Confirmed pairs open in a comparison slider.
5. **Report.** It builds an impact report whose summary is generated **only** from stored captions, tags, dates and confirmed pairs, with a timeline, sliders and an evidence table. The report downloads as print-ready HTML.
6. **Trace.** Every image can be followed back to its original Cloudinary asset, EXIF, raw AI output, model name and every transformation used to deliver it.

## Architecture

```mermaid
flowchart LR
    subgraph Input
        U[Upload page<br/>live mode] 
        S[scripts/seed_cloudinary.py<br/>one-off seeding]
    end
    U & S -->|original, untouched| C[(Cloudinary<br/>storage + delivery)]
    U & S -->|EXIF: time, GPS| X[gt/exif.py]
    U & S -->|downscaled copy| AI[gt/ai_provider.py<br/>Gemini vision + embeddings]
    AI --> AN[gt/analysis.py<br/>strict JSON schema<br/>parse fallback → needs_review]
    X & AN --> DB[(SQLite<br/>projects · assets · analyses<br/>pairs · transform_log)]
    SEED[seed/analysis.json<br/>pre-analyzed demo data] -->|DEMO_MODE| DB
    DB --> P1[Assets grid + filters]
    DB --> P2[Semantic search<br/>why-it-matched]
    DB --> P3[Pair scoring<br/>0.4 loc + 0.4 visual + 0.2 time<br/>human confirm/reject]
    DB --> P4[Report<br/>grounded summary · timeline · evidence]
    DB --> P5[Trace panel]
    C -->|transformation URLs<br/>thumb · compare · face blur · campaign card| P1 & P3 & P4 & P5
    P3 & P4 & P5 -.logged.-> T[transform_log]
```

**Stack:** Python 3.11 · Streamlit (multipage) · Cloudinary Python SDK · SQLite (plain `sqlite3`) + numpy cosine similarity · Google Gemini via `google-genai` (all provider code lives in `gt/ai_provider.py`) · `streamlit-image-comparison` · Pillow.

## Features

| Requirement | Feature | Status |
|---|---|---|
| Organize large collections | Projects, asset grid, filters by project / activity / capture date / flags | ✅ Implemented |
| Identify projects, activities, locations, signals | Vision model → caption, activity type, signals, tags (strict JSON schema); EXIF time + GPS | ✅ Implemented |
| | Parse failure → raw output stored, `needs_review` flag, pipeline continues | ✅ Implemented (tested) |
| AI metadata, tagging, semantic search | Embeddings of caption + tags; cosine search with "why it matched" | ✅ Implemented |
| | Keyword/tag fallback when no AI key is configured (clearly labelled) | ✅ Implemented |
| Compare before/after | Pair suggestion with per-factor breakdown; human confirm/reject; slider | ✅ Implemented (scoring tested) |
| Visual reports & campaign content | Report page: grounded summary (cached for demo), timeline, confirmed sliders, evidence table | ✅ Implemented |
| | Download as print-friendly HTML (browser *Print → Save as PDF* for PDF) | ✅ Implemented |
| | Campaign card: before/after side by side with Cloudinary layer + text overlays | ✅ Implemented |
| Traceability | Original URL, upload time, EXIF, analysis JSON, raw model output, model name, transformation chain, pair usage | ✅ Implemented |
| Responsible AI | Near-duplicate flag, missing GPS / date, capture-after-upload, people warning, face blur on delivery | ✅ Implemented (duplicates tested) |
| | Native PDF export | 🗓️ Planned |
| | Pixel-level change detection (in addition to embedding similarity) | 🗓️ Planned |
| | Additional AI providers (interface is isolated, only Gemini implemented) | 🗓️ Planned |
| | User accounts / roles, persistent hosted database | 🗓️ Planned |
| | Video evidence | 🗓️ Planned |

## Demo dataset

Four civic-infrastructure repairs in Kochi, Kerala, one before/after pair each:

| Project | Site (fictional) | Before → after (fictional dates) |
|---|---|---|
| Exposed electrical cable repair | Kakkanad | 2026-08-04 → 2026-08-08 (4 days) |
| Broken gutter cover replacement | Edappally | 2026-08-11 → 2026-08-17 (6 days) |
| Loose wiring rerouted into conduit | Vyttila | 2026-08-19 → 2026-08-23 (3 days) |
| Overgrown utility hatch restored | Fort Kochi | 2026-09-01 → 2026-09-06 (5 days) |

- **Provenance per image.** The *before* images are real photos. The *after* images are AI-generated or edited (`synthetic=true` in [`seed/metadata.csv`](seed/metadata.csv)).
- **How the app discloses it.** One short line in the sidebar on every page. Each image's **Trace** page shows its full provenance (real photo vs AI-generated/edited, and the metadata source). Exported reports and campaign cards carry a small "illustrative demo" footer. The full note lives in [`seed/dataset.json`](seed/dataset.json).
- **Locations and dates** come from `metadata.csv`, not from the files, which carry no EXIF. Each pair shares one location; each site is a different part of Kochi.
- **Sources** for each file are in [`seed/SOURCES.md`](seed/SOURCES.md).
- **Confirmed pairs** were supplied as pairs by the maintainer (`seed/confirmed_pairs.txt`). Because the *after* images are AI-generated/edited, a confirmed pair shows a visible difference only. It is never presented as a verified repair.

## How demo mode works

The public URL runs with **`DEMO_MODE=true`** (the default), so judges don't need to enter anything:

- The app loads **`seed/analysis.json`**, a pre-analyzed dataset produced once by `scripts/seed_cloudinary.py`. It holds Cloudinary public_ids, EXIF-derived metadata, AI captions, tags, signals, embeddings, reviewer-confirmed pairs and cached report summaries. Images are served from Cloudinary; no API secret is needed for delivery.
- On start (and whenever the seed file changes) the SQLite database is rebuilt from the seed.
- **Uploads and live AI analysis are disabled** and the Upload page says so.
- **Pair confirm/reject works for your browser session only**, so visitors can try it without changing the shared demo.
- **Search:** if a `GEMINI_API_KEY` secret is set on the deployment, the query is embedded for true semantic search; otherwise the app falls back to keyword/tag matching over the stored AI metadata **and says so on the page**.
- **Report summary:** the AI summary cached in the seed is shown with its model name and timestamp. If none is cached for a scope, a deterministic template summary is shown, labelled "no AI".

Live mode (`DEMO_MODE=false` + Cloudinary + Gemini keys) enables the Upload page, live analysis, recomputing pair suggestions and regenerating summaries.

## Setup and run

```bash
git clone https://github.com/PiSquareLabs/ground-truth-cloudinary.git
cd ground-truth-cloudinary
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env        # fill in keys only if you need live mode / seeding
streamlit run app.py
pytest -q                   # pair scoring, JSON-parse fallback, duplicate detection
```

### Building the demo seed (one-off, needs keys)

1. Put the images in `seed/images/` (JPEG/PNG/WebP).
2. Describe them in `seed/metadata.csv` with columns `filename, project, captured_at, lat, lng, role, synthetic` (`synthetic=true` means AI-generated or edited). Add `seed/projects.json` for project names and `seed/dataset.json` for the dataset note shown in the app.
3. Run `python scripts/seed_cloudinary.py`. It uploads originals to Cloudinary, applies the CSV metadata, analyzes each image, appends missing files to `seed/SOURCES.md`, prints pair suggestions and writes `seed/analysis.json`.
4. Review the suggestions. Either list approved pairs in `seed/confirmed_pairs.txt`, or pass `--confirm-by-role` to confirm suggested pairs whose CSV roles are before → after in the same project.
5. Run `python scripts/seed_cloudinary.py --report` (add `--confirm-by-role` again if you used it) to cache the AI report summaries. Commit `seed/`.

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `DEMO_MODE` | `true` | Read-only demo from `seed/analysis.json` |
| `CLOUDINARY_URL` | – | `cloudinary://key:secret@cloud_name`; needed for uploads / seeding |
| `CLOUDINARY_FOLDER` | `ground-truth` | Upload folder prefix |
| `AI_PROVIDER` | `gemini` | Only `gemini` is implemented |
| `GEMINI_API_KEY` | – | Analysis, embeddings, summaries; optional in demo (enables semantic query search) |
| `GEMINI_VISION_MODEL` | `gemini-3.8-flash` | Captions/tags/JSON and report summary |
| `GEMINI_FALLBACK_MODELS` | `gemini-3.7-flash,gemini-3.6-flash,gemini-3.5-flash-lite` | Tried in order if the primary model is overloaded or unavailable; the model actually used is recorded |
| `GEMINI_EMBED_MODEL` | `gemini-embedding-001` | 768-dim embeddings |
| `PAIR_W_LOCATION` / `PAIR_W_VISUAL` / `PAIR_W_TIME` | `0.4` / `0.4` / `0.2` | Pair score weights |
| `LOCATION_SCALE_M` | `150` | Distance (m) at which location proximity = 0.5 |
| `PAIR_MIN_SCORE` | `0.75` | Minimum score to suggest a pair |
| `DUPLICATE_HASH_BITS` | `32` | Max differing bits (of 256) in the pixel perceptual hash to flag a near-duplicate |
| `DUPLICATE_THRESHOLD` | `0.97` | Embedding-cosine fallback for images without a pixel hash |
| `DB_PATH` / `SEED_DIR` | `data/ground_truth.db` / `seed` | Storage locations |

Locally these come from `.env`; on Streamlit Cloud, from **Secrets** (see `.streamlit/secrets.toml.example`). Real keys are never committed (`.env` and `secrets.toml` are git-ignored).

## Deployment

**Primary: Streamlit Community Cloud** (live at the URL above). Main file `app.py`, Python 3.11, secrets `DEMO_MODE = "true"` and `GEMINI_API_KEY` (optional; enables semantic query search). No Cloudinary secret is needed for the read-only demo. Free apps sleep when idle; the first visit can take ~30 s to wake.
**Fallback: Hugging Face Space (Docker SDK).** Use `hf_space/Dockerfile` and `hf_space/README.md` (Space metadata). HF no longer offers the native Streamlit SDK for new Spaces, so Docker is used.

## Responsible AI

- Everything the model produces (captions, activity, signals, tags, summaries) is labelled **"AI-suggested"**, with the model name and time on the Trace page.
- The report summary is generated **only from stored facts** (the exact facts JSON is shown on the page). Counts and dates on the report are computed by code, not the model.
- The wording is deliberately limited to **"visible difference between confirmed paired images"**. The app never claims verified environmental improvement.
- Pairs are **suggested, never auto-confirmed**; a person decides.
- **Near-duplicates** are flagged using a perceptual hash of the pixels (caption embeddings were too coarse: two different drains got near-identical captions), including inside pair review.
- **Metadata checks:** no GPS, no capture date, capture date after upload date.
- **People:** the model reports whether people are visible; those images are flagged and delivered with Cloudinary's `e_blur_faces` transformation. The original is never modified.

## Design choices (simplest option, noted as required)

- Plain `sqlite3` instead of an ORM; embeddings stored as JSON, similarity in numpy.
- The demo DB is rebuilt from the committed seed file on start, because Streamlit Cloud's disk is temporary.
- "Visual similarity" in pair scoring is the cosine similarity of **embeddings of AI captions + tags + signals** (a semantic proxy), not pixel comparison.
- Missing GPS in the same project gives a neutral location score (0.5); a missing date gives a neutral time score (0.5).
- Pairs are only suggested within one project, but the activity type does not have to match: a “before” photo (bare soil, litter) often doesn't show the activity yet.
- For seed data, `metadata.csv` overrides EXIF (these files carry no EXIF). Uploads in live mode use EXIF.
- HTML report export instead of server-side PDF (no extra native dependencies; print to PDF from the browser).
- Demo-mode review decisions are stored in the browser session, not the shared DB.
- `numpy` pinned to 2.4.x, the last line with Python 3.11 wheels.

## Known limitations

- Visual similarity is semantic (caption/tag embeddings), so two different drains with similar captions can score high.
- Without an AI key, search falls back to keyword/tag matching, which cannot tell "blocked drain" from "clear drain" as well as semantic search can. Location and time factors offset this, and a human confirms.
- Face blur depends on Cloudinary's face detection and can miss small or partial faces.
- The demo database is temporary and shared per container; live-mode data is lost when a Cloud container restarts.
- Pairing compares all images with the same activity type (O(n²)). That's fine for hundreds of images, not tens of thousands.
- HEIC photos must be converted to JPEG before seeding or upload.
- Photos without EXIF date/GPS can only be paired if the uploader enters a date and location on the Upload page (the page asks for any that are missing).
- Free Streamlit Cloud apps sleep when idle; the first load can take ~30 s.

## Screenshots

See [`screenshots/`](screenshots/).

## License

Code: MIT. Seed images: before photos by the maintainer; after images AI-generated/edited. See `seed/SOURCES.md`.
