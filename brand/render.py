"""Render ScoutIQ brand assets from logo.svg and thumbnail.html into brand/.

    demo/.venv/bin/python brand/render.py

Writes logo-1024.png, logo-512.png, logo-wordmark.png, thumbnail-16x9.png (1920x1080)
and thumbnail-3x2.png (1500x1000).
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
WORDMARK = """<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@800&display=swap" rel="stylesheet">
<style>html,body{margin:0;background:transparent}
.w{display:inline-flex;align-items:center;gap:36px;padding:40px 56px;font-family:Inter,system-ui,sans-serif}
img{width:200px;height:200px}span{font-size:150px;font-weight:800;letter-spacing:-5px;color:#fff}b{color:#34d399}</style>
</head><body><div class="w"><img src="logo.svg"><span>Scout<b>IQ</b></span></div></body></html>"""


def main():
    (ROOT / "_wordmark.html").write_text(WORDMARK)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for size in (1024, 512):
            page = browser.new_page(viewport={"width": 512, "height": 512}, device_scale_factor=size / 512)
            page.goto((ROOT / "logo.svg").as_uri())
            page.screenshot(path=str(ROOT / f"logo-{size}.png"), omit_background=True)
            page.close()

        page = browser.new_page(viewport={"width": 1400, "height": 400})
        page.goto((ROOT / "_wordmark.html").as_uri(), wait_until="networkidle")
        page.locator(".w").screenshot(path=str(ROOT / "logo-wordmark.png"), omit_background=True)
        page.close()

        for name, (w, h), scale, cls in [("thumbnail-16x9.png", (1280, 720), 1.5, ""),
                                         ("thumbnail-3x2.png", (1200, 800), 1.25, "r32")]:
            page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=scale)
            page.goto((ROOT / "thumbnail.html").as_uri(), wait_until="networkidle")
            if cls:
                page.evaluate(f"document.body.classList.add('{cls}')")
            page.wait_for_timeout(300)
            page.screenshot(path=str(ROOT / name))
            page.close()
        browser.close()
    (ROOT / "_wordmark.html").unlink()
    for p in sorted(ROOT.glob("*.png")):
        print(p.name)


if __name__ == "__main__":
    main()
