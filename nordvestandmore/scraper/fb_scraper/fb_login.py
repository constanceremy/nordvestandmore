#!/usr/bin/env python3
"""
One-time Facebook login helper.
Opens a visible browser window so you can log in manually.
Saves session cookies to fb_cookies.json for the scraper to reuse.
"""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

COOKIES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fb_cookies.json")


def main():
    print("🔑 Facebook Login Helper")
    print("=" * 40)
    print("A browser window will open.")
    print("Log in to Facebook normally.")
    print("Once you see your feed, CLOSE the browser window.")
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # Visible browser!
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="en-US",
        )
        page = context.new_page()
        page.goto("https://www.facebook.com/login", wait_until="domcontentloaded")

        print("⏳ Waiting for you to log in... (close the browser when done)")

        # Wait for the browser to be closed by the user
        try:
            page.wait_for_event("close", timeout=300000)  # 5 min timeout
        except Exception:
            pass

        # Save cookies/session state
        context.storage_state(path=COOKIES_FILE)
        print(f"\n✅ Cookies saved to {COOKIES_FILE}")
        print("The scraper will now use these cookies automatically.")

        try:
            browser.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
