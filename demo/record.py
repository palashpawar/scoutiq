"""Drive ScoutIQ with Playwright and record the walkthrough, one scene per narration clip.

Each scene holds until its narration (demo/out/durations.json) has finished.
Writes demo/out/raw.webm and demo/out/marks.json (scene start/end on the video timeline).

    python demo/record.py [--base http://localhost:3000]
"""
import argparse
import json
import shutil
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"
W, H = 1440, 810
QUERY = ("Find three midfielders under age 25 who progress the ball well, contribute defensively, "
         "and have an estimated market value below €15 million.")


class Recorder:
    def __init__(self, page: Page, durations: dict, t0: float):
        self.page, self.dur, self.t0, self.marks = page, durations, t0, []

    def now(self) -> float:
        return round(time.monotonic() - self.t0, 2)

    def scene(self, sid: str):
        if self.marks:
            self.marks[-1]["end"] = self.now()
        self.marks.append({"id": sid, "start": self.now()})

    def hold_rest(self, pad=0.7):
        m = self.marks[-1]
        left = m["start"] + self.dur[m["id"]] + pad - self.now()
        if left > 0:
            self.page.wait_for_timeout(left * 1000)

    def finish(self):
        self.marks[-1]["end"] = self.now()


def smooth_scroll(page: Page, container: str | None, to, ms=1200):
    """Ease-scroll the window (container=None) or a CSS-selected element to a Playwright selector or pixel offset."""
    if not isinstance(to, (int, float)):
        to = page.locator(to).first.evaluate("e => e.getBoundingClientRect().top")
        to = page.evaluate("""([sel, top]) => {
            const el = sel ? document.querySelector(sel) : document.scrollingElement;
            const base = sel ? el.getBoundingClientRect().top : 0;
            return top - base + el.scrollTop - 90;
        }""", [container, to])
    page.evaluate("""([sel, target, ms]) => {
        const el = sel ? document.querySelector(sel) : document.scrollingElement;
        const from = el.scrollTop, t0 = performance.now();
        const step = (t) => { const k = Math.min(1, (t - t0) / ms);
            el.scrollTop = from + (target - from) * (1 - Math.cos(Math.PI * k)) / 2;
            if (k < 1) requestAnimationFrame(step); };
        requestAnimationFrame(step);
    }""", [container, to, ms])
    page.wait_for_timeout(ms + 150)


def card(page: Page, name: str):
    return page.locator("article", has_text=name).first


def wait_results(page: Page, name: str):
    page.wait_for_selector(f"article:has-text(\"{name}\")", timeout=120_000)
    page.wait_for_timeout(500)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:3000")
    args = ap.parse_args()
    durations = json.loads((OUT / "durations.json").read_text())
    vids = OUT / "video"
    shutil.rmtree(vids, ignore_errors=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport={"width": W, "height": H}, color_scheme="dark", device_scale_factor=1,
                                  record_video_dir=str(vids), record_video_size={"width": W, "height": H})
        page = ctx.new_page()
        t0 = time.monotonic()  # video timeline starts with the page
        rec = Recorder(page, durations, t0)
        page.goto(args.base)
        page.wait_for_selector("text=Try an example")
        page.wait_for_timeout(800)

        rec.scene("intro")
        page.wait_for_timeout(5000)
        smooth_scroll(page, None, "text=1 · Interpret", 1800)
        page.wait_for_timeout(max(1000, (rec.dur["intro"] - 10) * 1000))
        smooth_scroll(page, None, 0, 1500)
        page.hover("text=Find three midfielders under age 25")
        rec.hold_rest(pad=0.3)

        rec.scene("ask")
        page.click("#prompt")
        page.type("#prompt", QUERY, delay=28)
        page.wait_for_timeout(400)
        page.keyboard.press("Enter")
        wait_results(page, "Oriol Romeu")
        rec.hold_rest(pad=0.3)

        rec.scene("results")
        page.click("summary:has-text('Scoring weights')")
        page.wait_for_timeout(1200)
        smooth_scroll(page, None, "article", 1800)
        page.hover("article:has-text('Oriol Romeu')")
        rec.hold_rest()

        rec.scene("evidence")
        card(page, "Oriol Romeu").get_by_role("button", name="Why this player?").click()
        page.wait_for_selector("#drawer-title")
        page.wait_for_timeout(2200)
        drawer = "aside.relative"
        smooth_scroll(page, drawer, "text=How the score is built", 1400)
        page.wait_for_timeout(3500)
        smooth_scroll(page, drawer, "text=Strengths and trade-offs", 1400)
        page.wait_for_timeout(4000)
        smooth_scroll(page, drawer, "text=Value context", 1600)
        rec.hold_rest()

        rec.scene("refine")
        page.get_by_role("button", name="Add to comparison").click()
        page.wait_for_timeout(700)
        page.keyboard.press("Escape")
        smooth_scroll(page, None, 0, 900)
        smooth_scroll(page, None, "article", 900)
        card(page, "Jonjo Shelvey").get_by_role("button", name="+ Compare").click()
        page.wait_for_timeout(900)
        smooth_scroll(page, None, 0, 900)
        page.get_by_role("button", name="Increase the budget to €25 million").click()
        wait_results(page, "Kanté")
        page.wait_for_timeout(600)
        smooth_scroll(page, None, "article", 1200)
        rec.hold_rest(pad=0.3)

        rec.scene("compare")
        card(page, "Kanté").get_by_role("button", name="+ Compare").click()
        page.wait_for_timeout(800)
        page.get_by_role("button", name="Compare 3").click()
        page.wait_for_selector("#compare-title")
        page.wait_for_timeout(3500)
        smooth_scroll(page, "[aria-labelledby=compare-title]", "text=Interceptions per 90", 1600)
        page.wait_for_timeout(3000)
        smooth_scroll(page, "[aria-labelledby=compare-title]", "text=Ball recoveries per 90", 1400)
        rec.hold_rest()

        rec.scene("defence")
        page.keyboard.press("Escape")
        smooth_scroll(page, None, 0, 800)
        page.get_by_role("button", name="Prioritize defensive contribution").click()
        page.wait_for_selector("text=Profile ≈ Defensive midfielder", timeout=120_000)
        page.wait_for_timeout(500)
        if not page.locator("details[open] >> text=Scoring weights").count():
            page.click("summary:has-text('Scoring weights')")
        smooth_scroll(page, None, "text=Changed:", 1200)
        rec.hold_rest()

        rec.scene("outro")
        smooth_scroll(page, None, 0, 1200)
        rec.hold_rest(pad=2.5)
        rec.finish()

        video = page.video
        ctx.close()
        browser.close()
        shutil.move(video.path(), OUT / "raw.webm")
    (OUT / "marks.json").write_text(json.dumps(rec.marks, indent=1))
    for m in rec.marks:
        print(f"{m['id']:10} {m['start']:6.1f} → {m['end']:6.1f}  ({m['end'] - m['start']:.1f}s, narration {durations[m['id']]:.1f}s)")


if __name__ == "__main__":
    main()
