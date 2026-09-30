"""Drive the local Ground Truth app and record it via CDP screencast, scene-timed to the narration."""
import asyncio, base64, json, os, re, time
from pathlib import Path
from playwright.async_api import async_playwright

B = "http://localhost:8501"
HERE = Path(__file__).parent
FR = HERE / "frames"
FR.mkdir(exist_ok=True)
for f in FR.glob("*.jpg"):
    f.unlink()
N = json.load(open(HERE / "narration.json"))
D = json.load(open(HERE / "durations.json"))

OVERLAY_JS = r"""
(() => {
  if (document.getElementById('gt-cursor')) return;
  const add = () => {
    const c = document.createElement('div'); c.id = 'gt-cursor';
    c.style.cssText = 'position:fixed;left:-50px;top:-50px;width:22px;height:22px;border-radius:50%;' +
      'background:rgba(46,125,50,.35);border:2px solid #2E7D32;z-index:2147483647;pointer-events:none;' +
      'transform:translate(-50%,-50%);transition:width .12s,height .12s,background .12s';
    const cap = document.createElement('div'); cap.id = 'gt-cap';
    cap.style.cssText = 'position:fixed;left:50%;bottom:26px;transform:translateX(-50%);max-width:1100px;' +
      'padding:10px 22px;border-radius:10px;background:rgba(20,24,28,.82);color:#fff;font:500 21px/1.4 ' +
      '"Source Sans Pro","Source Sans 3",system-ui,sans-serif;text-align:center;z-index:2147483646;' +
      'pointer-events:none;opacity:0;transition:opacity .2s';
    document.documentElement.append(c, cap);
  };
  if (document.body) add(); else document.addEventListener('DOMContentLoaded', add);
  window.__gtCur = (x, y, down) => { const c = document.getElementById('gt-cursor'); if (!c) return;
    c.style.left = x + 'px'; c.style.top = y + 'px';
    c.style.width = c.style.height = down ? '16px' : '22px';
    c.style.background = down ? 'rgba(46,125,50,.7)' : 'rgba(46,125,50,.35)'; };
  window.__gtCap = (t) => { const e = document.getElementById('gt-cap'); if (!e) return;
    e.textContent = t; e.style.opacity = t ? 1 : 0; };
})();
"""

CARD = """<!doctype html><html><head><meta charset="utf-8"><style>
body{margin:0;height:100vh;display:flex;align-items:center;justify-content:center;
background:linear-gradient(135deg,#f3f7f3 0%%,#e3efe4 100%%);font-family:"Source Sans Pro",system-ui,sans-serif;color:#1b2a1e}
.w{max-width:1100px;padding:0 60px} h1{font-size:88px;margin:0 0 10px;letter-spacing:-1px}
.t{font-size:34px;color:#2E7D32;margin:0 0 36px;font-weight:600} p{font-size:26px;line-height:1.5;margin:8px 0;color:#34463a}
.s{margin-top:40px;font-size:20px;color:#5c6f61}
</style></head><body><div class="w">%s</div></body></html>"""

INTRO = CARD % ("<h1>🌱 Ground Truth</h1><div class='t'>Before/after field evidence you can trace, built on Cloudinary</div>"
                "<p>Organize field photos · search them · confirm before/after pairs · share a traceable report</p>"
                "<div class='s'>Demo dataset: before photos are real; after images are AI-edited; sites and dates are illustrative.</div>")
OUTRO = CARD % ("<h1>🌱 Ground Truth</h1><div class='t'>Organized, traceable field evidence</div>"
                "<p>✔ Near-duplicate and missing date/location flags</p><p>✔ Faces blurred on delivery</p>"
                "<p>✔ Visible difference between confirmed pairs, never claimed impact</p>"
                "<p>✔ Every image traced back to its Cloudinary original</p>"
                "<div class='s'>Streamlit · Cloudinary · Gemini &nbsp;|&nbsp; github.com/PiSquareLabs/ground-truth-cloudinary</div>")


def chunks(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text)
    out = []
    for p in parts:
        while len(p) > 95:
            cut = p.rfind(",", 0, 95)
            cut = cut if cut > 30 else p.rfind(" ", 0, 95)
            out.append(p[:cut + 1].strip()); p = p[cut + 1:].strip()
        if p:
            out.append(p)
    return out


class Rec:
    def __init__(self, page):
        self.page, self.x, self.y = page, 800, 450
        self.t0, self.cues, self.scenes, self.cur = None, [], [], ""

    async def overlay(self):
        await self.page.evaluate(OVERLAY_JS)
        await self.page.evaluate(f"window.__gtCur({self.x},{self.y},false)")
        await self.page.evaluate("t => window.__gtCap(t)", self.cur)

    async def captions(self, key, start):
        cs = chunks(N[key]); total = sum(len(c) for c in cs); t = start
        for c in cs:
            d = D[key] * len(c) / total
            self.cues.append((t - self.t0, t + d - self.t0, c)); self.cur = c
            try:
                await self.page.evaluate("t => window.__gtCap && window.__gtCap(t)", c)
            except Exception:
                pass
            await asyncio.sleep(max(0, t + d - time.time())); t += d
        self.cur = ""
        try:
            await self.page.evaluate("window.__gtCap && window.__gtCap('')")
        except Exception:
            pass

    async def scene(self, key, actions, tail=0.6):
        start = time.time()
        self.scenes.append((key, start - self.t0))
        cap = asyncio.create_task(self.captions(key, start))
        await actions()
        await cap
        await asyncio.sleep(max(0, start + D[key] + tail - time.time()))

    async def move(self, x, y, steps=18):
        x0, y0 = self.x, self.y
        for i in range(1, steps + 1):
            k = i / steps; e = k * k * (3 - 2 * k)
            cx, cy = x0 + (x - x0) * e, y0 + (y - y0) * e
            await self.page.mouse.move(cx, cy)
            await self.page.evaluate(f"window.__gtCur && window.__gtCur({cx},{cy},false)")
            await asyncio.sleep(0.016)
        self.x, self.y = x, y

    async def click(self, loc, pause=0.35):
        await loc.scroll_into_view_if_needed()
        b = await loc.bounding_box()
        await self.move(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2)
        await asyncio.sleep(0.15)
        await self.page.evaluate(f"window.__gtCur({self.x},{self.y},true)")
        await self.page.mouse.down(); await asyncio.sleep(0.08); await self.page.mouse.up()
        await self.page.evaluate(f"window.__gtCur({self.x},{self.y},false)")
        await asyncio.sleep(pause)

    async def scroll(self, dy, steps=20, x=950, y=520):
        await self.move(x, y, 10)
        for _ in range(steps):
            await self.page.mouse.wheel(0, dy / steps); await asyncio.sleep(0.03)
        await asyncio.sleep(0.3)

    async def type(self, loc, text):
        await self.click(loc)
        await loc.press("Control+A"); await loc.press("Backspace")
        for ch in text:
            await self.page.keyboard.type(ch); await asyncio.sleep(0.055)
        await asyncio.sleep(0.2); await loc.press("Enter")


async def settle(page, t=1.2):
    await asyncio.sleep(0.3)
    try:
        await page.wait_for_function("!document.querySelector('[data-testid=\"stStatusWidget\"]')", timeout=15000)
    except Exception:
        pass
    await asyncio.sleep(t)


async def main():
    async with async_playwright() as p:
        opts = {"args": ["--hide-scrollbars", *os.environ.get("CHROMIUM_ARGS", "").split()]}
        if os.environ.get("CHROMIUM_PATH"):
            opts["executable_path"] = os.environ["CHROMIUM_PATH"]
        if os.environ.get("HTTPS_PROXY"):
            opts["proxy"] = {"server": os.environ["HTTPS_PROXY"], "bypass": "localhost,127.0.0.1"}
        br = await p.chromium.launch(**opts)
        ctx = await br.new_context(viewport={"width": 1600, "height": 900}, device_scale_factor=1.2, accept_downloads=True)
        await ctx.add_init_script(OVERLAY_JS)
        page = await ctx.new_page()
        R = Rec(page)
        side = lambda name: page.locator('[data-testid="stSidebarNav"] a', has_text=name)

        # Warm up: load every page once so images are cached, then go to the intro card.
        for path in ["", "assets", "pairs", "report", "trace"]:
            await page.goto(f"{B}/{path}"); await settle(page, 4)
        await page.set_content(INTRO); await R.overlay()

        cdp = await ctx.new_cdp_session(page)
        frames = []

        async def on_frame(ev):
            ts = ev["metadata"]["timestamp"]
            fn = FR / f"{len(frames):06d}.jpg"
            fn.write_bytes(base64.b64decode(ev["data"])); frames.append((ts, fn.name))
            try:
                await cdp.send("Page.screencastFrameAck", {"sessionId": ev["sessionId"]})
            except Exception:
                pass
        cdp.on("Page.screencastFrame", lambda ev: asyncio.ensure_future(on_frame(ev)))
        await cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 92, "maxWidth": 1920, "maxHeight": 1080})
        await asyncio.sleep(0.5)
        R.t0 = time.time()

        async def intro():
            await R.move(1000, 600, 30)
        await R.scene("intro", intro, tail=0.4)

        async def home():
            await page.goto(f"{B}/"); await settle(page, 0.8); await R.overlay()
            await R.move(760, 560, 25); await asyncio.sleep(1.5)            # 4 steps
            await R.scroll(330); await asyncio.sleep(1.2)
            await R.move(1000, 420, 25); await asyncio.sleep(2.5)           # metrics
            await R.scroll(-330); await asyncio.sleep(0.3)
            await R.move(900, 345, 25)                                      # banner
        await R.scene("home", home)

        async def library():
            await R.click(side("Evidence library")); await settle(page, 0.8)
            await R.scroll(420); await asyncio.sleep(1.2)
            await R.move(560, 470, 20); await asyncio.sleep(2.2)            # AI caption
            await R.move(520, 300, 20); await asyncio.sleep(2.2)            # thumbnail
            await R.scroll(-420); await asyncio.sleep(0.4)
            await R.click(page.locator("button", has_text="Filters").first, pause=0.8)
            vy = page.get_by_test_id("stPopoverBody").get_by_text("Loose wiring rerouted into conduit, Vyttila", exact=True)
            await R.click(vy, pause=0.6); await settle(page, 0.6)
            await page.keyboard.press("Escape"); await asyncio.sleep(1.8)
            await R.click(page.locator("button", has_text="Filters").first, pause=0.5)
            await R.click(vy, pause=0.4); await settle(page, 0.4)
            await page.keyboard.press("Escape"); await settle(page, 0.3)
        await R.scene("library", library)

        async def search():
            box = page.get_by_placeholder("e.g. open drain next to a road")
            await R.move(850, 312, 20); await asyncio.sleep(0.8)
            await R.type(box, "tangled wires on a wall"); await settle(page, 0.5)
            await R.move(620, 460, 20); await asyncio.sleep(1.6)             # keyword notice
            await R.scroll(420); await asyncio.sleep(0.4)
            await R.move(560, 640, 20); await asyncio.sleep(3.0)             # why it matched
            await R.scroll(-420)
            await R.type(box, "damaged drain cover"); await settle(page, 0.5)
            await R.scroll(420); await asyncio.sleep(0.4)
        await R.scene("search", search, tail=1.2)

        async def pairs():
            await R.click(side("Review pairs")); await settle(page, 2.0)
            await R.move(700, 300, 20); await asyncio.sleep(1.2)
            fr = page.locator("iframe").first
            await fr.scroll_into_view_if_needed(); await asyncio.sleep(0.8)
            b = await fr.bounding_box()
            cx, cy = b["x"] + b["width"] / 2, b["y"] + b["height"] / 2
            await R.move(cx, cy, 25); await asyncio.sleep(0.4)
            await page.evaluate(f"window.__gtCur({cx},{cy},true)"); await page.mouse.down()
            for tx in (b["x"] + b["width"] * 0.12, b["x"] + b["width"] * 0.88, b["x"] + b["width"] * 0.5):
                await R.move(tx, cy, 45)
                await page.evaluate(f"window.__gtCur({R.x},{R.y},true)"); await asyncio.sleep(0.3)
            await page.mouse.up(); await page.evaluate(f"window.__gtCur({R.x},{R.y},false)")
        await R.scene("pairs", pairs)

        async def breakdown():
            await R.click(page.get_by_text("Score and Cloudinary URLs").first, pause=0.6)
            await R.scroll(380); await asyncio.sleep(2.2)
            await R.click(page.get_by_text("Campaign card").first, pause=0.6); await asyncio.sleep(0.8)
            await R.scroll(520); await asyncio.sleep(0.4)
        await R.scene("breakdown", breakdown, tail=1.6)

        async def report():
            await R.click(side("Impact report")); await settle(page, 0.8)
            await R.move(950, 420, 25); await asyncio.sleep(1.6)              # counts
            await R.move(710, 760, 25); await asyncio.sleep(2.0)              # summary
            await R.move(1300, 660, 25); await asyncio.sleep(2.4)             # green check
            await R.click(page.get_by_role("tab", name="Timeline"), pause=0.6)
            await R.scroll(380); await asyncio.sleep(0.8); await R.scroll(-380)
            await R.click(page.get_by_role("tab", name="Evidence table"), pause=1.8)
            async with page.expect_download() as dl:
                await R.click(page.locator("button", has_text="Download report").first, pause=0.4)
            await dl.value
        await R.scene("report", report)

        async def trace():
            await page.goto(f"{B}/trace?asset=broken-gutter-cover-replacement-edappally-gutter-cover-before")
            await settle(page, 0.5); await R.overlay()
            await R.move(1200, 540, 20); await asyncio.sleep(0.8)
            await R.click(page.get_by_role("tab", name="2 · Capture"), pause=2.2)
            await R.click(page.get_by_role("tab", name="3 · AI analysis"), pause=2.6)
            await R.click(page.get_by_role("tab", name="4 · Transformations"), pause=0.6)
            await R.move(1250, 560, 20)
        await R.scene("trace", trace, tail=1.2)

        async def outro():
            await asyncio.sleep(1.0)
            await page.set_content(OUTRO); await R.overlay()
        await R.scene("outro", outro, tail=2.5)

        end = time.time()
        await cdp.send("Page.stopScreencast"); await asyncio.sleep(0.5)
        await br.close()

    json.dump({"t0": R.t0, "end": end, "frames": frames, "scenes": R.scenes, "cues": R.cues},
              open(HERE / "timeline.json", "w"))
    print("frames", len(frames), "duration", round(end - R.t0, 1))


asyncio.run(main())
