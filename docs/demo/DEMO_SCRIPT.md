# 3-minute demo script

The recorded video is [`ground-truth-demo.mp4`](ground-truth-demo.mp4) (2:41, 1080p, narrated, with burned-in
captions; [`ground-truth-demo.srt`](ground-truth-demo.srt) holds the same captions for YouTube and similar sites).
The page names below match the current app: Home → Evidence library → Review pairs → Impact report → Trace an image.

Free Streamlit apps go to sleep when idle, so open the live link a minute before you present.

**0:00–0:15 · Problem.** "NGOs have thousands of scattered field photos. When a funder asks 'what changed?', someone
digs through phones by hand. Ground Truth turns those photos into organized, traceable evidence, built on Cloudinary."

**0:15–0:30 · Home.** Point at the four steps (Collect, Explore, Review, Share) and the counts: 4 projects, 8 images,
4 confirmed pairs. "The banner says it upfront: the after images are AI-edited, and the sites and dates are illustrative."

**0:30–0:55 · Evidence library.** "Every photo is stored on Cloudinary and grouped by project. The AI wrote each caption
and activity type, and they're labelled AI-suggested." Point at a thumbnail: "These are Cloudinary transformations:
auto-crop, auto-quality, auto-format." Open **Filters** and tick a project to show filtering, then untick it.

**0:55–1:15 · Search** (same page). Type "tangled wires on a wall", then "damaged drain cover". Every result says why it
matched. With `GEMINI_API_KEY` set, search is by meaning (embeddings). Without a key, the app falls back to
keyword/tag matching and shows a notice saying so; the recorded video uses the key-free mode and says that.

**1:15–1:45 · Review pairs.** "The system suggests before/after pairs from location, visual similarity and time order.
It never auto-confirms; a person decides." Drag the slider on the Vyttila wiring pair. Expand **Score and Cloudinary
URLs** for the score breakdown and the exact URLs, then **Campaign card**: "a shareable image built entirely from
Cloudinary overlays."

**1:45–2:05 · Impact report.** "The counts come from the data, not the AI. The summary is written only from stored
facts, and every image it cites is checked to exist; the green check shows that." Open the **Timeline** and
**Evidence table** tabs, then click **Download report (HTML)**.

**2:05–2:22 · Trace an image.** Trace the Edappally gutter "before" image. Walk the tabs: 1 · Original (the Cloudinary
original), 2 · Capture (date, GPS, metadata source), 3 · AI analysis (full AI output and model), 4 · Transformations
(every Cloudinary URL the app delivered is logged).

**2:22–2:41 · Responsible AI.** "It flags near-duplicates and missing location or date, blurs faces on delivery, and
never claims verified impact. It only shows the visible difference between confirmed pairs. In this demo, the 'after'
images are AI-edited and the sites are illustrative, and the app says so."
