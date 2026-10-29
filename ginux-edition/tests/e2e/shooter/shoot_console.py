"""Capture the ThoxOS web console (ttyd) in headless Chromium.

Usage: shoot_console.py URL USER PASSWORD OUT_PNG WAIT_SECONDS [COMMAND...]
Opens the console with HTTP basic credentials at 1280x800, waits for the VM
to boot (the page itself runs the boot), types each COMMAND followed by Enter
with a pause for its output, and saves one PNG.
"""
import sys
import time

from playwright.sync_api import sync_playwright


def main() -> int:
    url, user, password, out, wait = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], float(sys.argv[5])
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/usr/bin/chromium", args=["--no-sandbox"])
        page = browser.new_page(
            viewport={"width": 1280, "height": 800},
            http_credentials={"username": user, "password": password},
            color_scheme="dark",
        )
        page.goto(url, wait_until="networkidle")
        time.sleep(wait)
        page.click("body")
        for command in sys.argv[6:]:
            page.keyboard.type(command, delay=60)
            page.keyboard.press("Enter")
            time.sleep(25)
        page.screenshot(path=out)
        browser.close()
    print(f"shooter: saved {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
