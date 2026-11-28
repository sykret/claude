"""Screenshot rc-playground.html with Playwright (light + dark) and check for JS errors."""
import pathlib
import sys

from playwright.sync_api import sync_playwright

here = pathlib.Path(__file__).resolve().parent
page_url = (here / "rc-playground.html").as_uri()

with sync_playwright() as p:
    browser = p.chromium.launch()
    errors = []
    for scheme in ("light", "dark"):
        page = browser.new_page(viewport={"width": 1000, "height": 640},
                                color_scheme=scheme, device_scale_factor=2)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(page_url)
        page.fill("#r", "4")  # move the R slider to 10 kΩ
        page.dispatch_event("#r", "input")
        print(scheme, "fc =", page.inner_text("#fc"), "tau =", page.inner_text("#tau"))
        page.screenshot(path=str(here / f"rc-playground-{scheme}.png"), full_page=True)
        page.close()
    browser.close()

if errors:
    sys.exit("JS errors: " + "; ".join(errors))
print("ok")
