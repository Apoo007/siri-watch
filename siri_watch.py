import json, os, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

LOCATIONS = os.getenv("LOCATIONS", "aarhus").split(",")
NTFY_TOPIC = os.environ["NTFY_TOPIC"]
BEFORE = os.getenv("BEFORE", "")  # fx 2026-12-20. Tom = alle dage
STATE = Path("state.json")
NAMES = {"aarhus": "Aarhus", "jacobsens": "København", "odense": "Odense",
         "aalborg": "Aalborg", "esbjerg": "Esbjerg", "aabenraa": "Sønderborg"}
BOOK_URL = "https://scandic.cleverq.de/public/locations/siri_dk/index.html?lang=da"

def check(page, loc):
    page.goto(f"https://scandic.cleverq.de/public/appointments/{loc}/index.html?lang=da")
    page.get_by_text("Ansøger efter udlændingeloven", exact=True).first.click()
    page.get_by_text("Ansøg om tilbagerejsetilladelse").first.click()
    with page.expect_response(lambda r: "available_days" in r.url, timeout=30000) as resp:
        page.get_by_text("Fortsæt", exact=True).first.click()
    data = resp.value.json(); print(loc, "status", resp.value.status, data)
    return sorted(d["day"] for d in data.get("available_days", []))

def notify(msg):
    req = urllib.request.Request(
        f"https://ntfy.sh/{NTFY_TOPIC}", data=msg.encode("utf-8"),
        headers={"Title": "SIRI: ledig tid", "Priority": "high", "Click": BOOK_URL})
    urllib.request.urlopen(req)

old = json.loads(STATE.read_text()) if STATE.exists() else {}
new, lines = {}, []

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(locale="da-DK", timezone_id="Europe/Copenhagen", user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
    for loc in LOCATIONS:
        try:
            days = check(page, loc)
        except Exception as e:
            print(loc, "fejl:", e)
            new[loc] = old.get(loc, [])
            continue
        if BEFORE:
            days = [d for d in days if d < BEFORE]
        new[loc] = days
        fresh = [d for d in days if d not in old.get(loc, [])]
        print(loc, days)
        if fresh:
            lines.append(f"{NAMES.get(loc, loc)}: {', '.join(fresh[:5])}")
    browser.close()

STATE.write_text(json.dumps(new, indent=1))
if lines:
    notify("Nye ledige dage:\n" + "\n".join(lines))
