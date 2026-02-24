#!/usr/bin/env python3
"""
Import Instagram session from your browser's sessionid cookie.

How to get your sessionid:
  1. Open Instagram in your browser (Chrome/Safari/Firefox)
  2. Make sure you're logged in
  3. Open Developer Tools (Cmd+Option+I or F12)
  4. Go to Application → Cookies → https://www.instagram.com
  5. Find the cookie named "sessionid" and copy its value
  6. Run this script and paste it

This creates an instaloader-compatible session file and prints the
base64-encoded version you can paste into the IG_SESSION_B64 GitHub secret.
"""
import base64
import os
import pickle
import sys
from pathlib import Path



def main():
    # Get the username
    username = os.environ.get("IG_USERNAME", "")
    if not username:
        username = input("Instagram username: ").strip()
    if not username:
        sys.exit("No username provided")

    # Get the sessionid cookie
    print()
    print("📋 Paste your Instagram 'sessionid' cookie value below.")
    print("   (from DevTools → Application → Cookies → instagram.com)")
    print()
    session_id = input("sessionid: ").strip()
    if not session_id:
        sys.exit("No sessionid provided")

    # Fetch a csrftoken from Instagram (needed by instaloader)
    import requests as req
    print("\n🔄 Fetching csrftoken from Instagram...")
    try:
        resp = req.get(
            "https://www.instagram.com/",
            headers={"User-Agent": "Mozilla/5.0"},
            cookies={"sessionid": session_id},
            timeout=10,
        )
        csrf = resp.cookies.get("csrftoken", "")
    except Exception:
        csrf = ""

    if not csrf:
        print("   Could not auto-fetch csrftoken.")
        print("   Copy it from DevTools → Cookies → instagram.com → csrftoken")
        csrf = input("csrftoken: ").strip()

    if not csrf:
        sys.exit("No csrftoken — cannot continue")

    print(f"   csrftoken: {csrf[:8]}... ✅")

    # Build a cookie dict — instaloader expects a plain dict
    cookie_dict = {
        "sessionid": session_id,
        "csrftoken": csrf,
    }

    # Save the session file in instaloader format (pickled dict)
    session_dir = Path.home() / ".config" / "instaloader"
    session_dir.mkdir(parents=True, exist_ok=True)
    session_file = session_dir / f"session-{username}"

    with open(session_file, "wb") as f:
        os.chmod(str(session_file), 0o600)
        pickle.dump(cookie_dict, f)

    print(f"\n✅ Session saved to {session_file}")

    # Quick test: can we load a profile with this session?
    print("\n🔍 Testing session...")
    try:
        import instaloader
        L = instaloader.Instaloader(max_connection_attempts=1)
        L.load_session_from_file(username, str(session_file))

        # Try loading a public profile
        profile = instaloader.Profile.from_username(L.context, "davescph")
        print(f"   Profile load: ✅ ({profile.full_name})")

        # Try fetching posts (this is what was failing)
        try:
            posts = []
            for post in profile.get_posts():
                posts.append(post)
                if len(posts) >= 1:
                    break
            if posts:
                print(f"   Post fetch:   ✅ (got {len(posts)} post)")
            else:
                print("   Post fetch:   ⚠️ (0 posts — may still work for other accounts)")
        except Exception as e:
            print(f"   Post fetch:   ❌ ({e})")
            print("   The session cookie may be expired or invalid.")
            print("   Make sure you're using a fresh sessionid from a logged-in browser.")
            return

    except ImportError:
        print("   (instaloader not installed, skipping test)")

    # Base64 encode for GitHub secret
    with open(session_file, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()

    print(f"\n📋 Base64-encoded session (copy this for IG_SESSION_B64 GitHub secret):\n")
    print(b64)
    print()
    print(f"   Length: {len(b64)} chars")
    print()
    print("Next steps:")
    print("  1. Copy the base64 string above")
    print("  2. Go to GitHub → Settings → Secrets → Actions")
    print("  3. Update IG_SESSION_B64 with the new value")
    print("  4. Re-enable the Instagram Drip Scrape workflow")
    print("  5. Trigger it manually to test")


if __name__ == "__main__":
    main()
