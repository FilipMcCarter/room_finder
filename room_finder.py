import os
import requests
import cloudscraper
from bs4 import BeautifulSoup
import sys
import json
 
# -------- CONFIG --------
PARARIUS_URL = "https://www.pararius.com/apartments/eindhoven/0-800"
KAMERNET_URL = "https://kamernet.nl/en/for-rent/room-eindhoven"
 
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1504047942401790012/YJV4UgJRrXh_ah90e4cBNGn5JNatOWAV0Dho5k5GRXZKjNEw8XSEHCCBDwdOWUjxzwda"
if not DISCORD_WEBHOOK:
    print("Error: DISCORD_WEBHOOK environment variable not set.")
    sys.exit(1)
 
SEEN_FILE = "seen_links.txt"
 
# -------- CITY FILTER --------
# Pararius sometimes includes nearby towns in Eindhoven searches — block them all.
BLOCKED_CITIES = [
    "helmond", "veldhoven", "waalre", "best", "geldrop", "nuenen",
    "mierlo", "deurne", "someren", "asten", "heeze", "leende",
    "bergeijk", "eersel", "oirschot", "son en breugel", "son",
    "gemert", "laarbeek", "meierijstad",
]
 
def is_eindhoven_only(location: str) -> bool:
    """Return True only if location is Eindhoven and not a blocked nearby city."""
    loc = location.lower()
    if any(city in loc for city in BLOCKED_CITIES):
        return False
    return "eindhoven" in loc or loc == ""  # empty = unknown, allow through
 
# -------- LOAD SEEN --------
if os.path.exists(SEEN_FILE):
    with open(SEEN_FILE, "r") as f:
        seen = set(line.strip() for line in f)
else:
    seen = set()
 
def save_link(link):
    with open(SEEN_FILE, "a") as f:
        f.write(link + "\n")
 
# -------- DISCORD --------
def send(title, price, link, source):
    msg = f"**{source}**\n{title}\nPrice: {price}\n{link}"
    try:
        res = requests.post(DISCORD_WEBHOOK, json={"content": msg})
        if res.status_code == 204:
            print(f"  v Sent to Discord: {title}")
        else:
            print(f"  Discord error: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"  Discord exception: {e}")
 
def send_test_message():
    try:
        res = requests.post(DISCORD_WEBHOOK, json={"content": "Bot started (v5 - Eindhoven only)"})
        if res.status_code == 204:
            print("Test message sent to Discord.", flush=True)
        else:
            print(f"Failed to send test message. Status: {res.status_code}", flush=True)
    except Exception as e:
        print(f"Test message exception: {e}", flush=True)
 
# -------- PARARIUS --------
def check_pararius(scraper):
    new_items = []
    print(f"\n[Pararius] Fetching: {PARARIUS_URL}")
    res = scraper.get(PARARIUS_URL)
    print(f"[Pararius] Status: {res.status_code}")
 
    if res.status_code != 200:
        print(f"[Pararius] Blocked. Snippet:\n{res.text[:300]}")
        return new_items
 
    soup = BeautifulSoup(res.text, "html.parser")
    listings = soup.select(".listing-search-item")
    print(f"[Pararius] Found {len(listings)} listing cards.")
 
    if len(listings) == 0:
        print("[Pararius] DEBUG - page title:", soup.title.string if soup.title else "N/A")
        print("[Pararius] DEBUG - HTML snippet (first 1000 chars):")
        print(res.text[:1000])
 
    for item in listings:
        title_tag = item.select_one(".listing-search-item__link--title")
        price_tag = item.select_one(".listing-search-item__price")
        if not title_tag or not price_tag:
            continue
 
        href = title_tag.get("href", "")
        link = "https://www.pararius.com" + title_tag.get("href", "")
        title = title_tag.get_text(strip=True)
        price = price_tag.get_text(strip=True)
 
        # Extract location text — Pararius puts city in a sub-element
        location_tag = item.select_one(".listing-search-item__location")
        location = location_tag.get_text(strip=True) if location_tag else href
 
        if not is_eindhoven_only(location):
            print(f"  [Pararius] Skipped (not Eindhoven): {title} | {location}")
            continue
 
        if link not in seen:
            seen.add(link)
            save_link(link)
            new_items.append((title, price, link, "Pararius"))
 
    return new_items
 
# -------- KAMERNET --------
def _find_listings_in_next_data(obj, depth=0):
    """Recursively search Next.js JSON for an array that looks like listings."""
    if depth > 10:
        return []
    if isinstance(obj, list) and len(obj) > 0:
        first = obj[0]
        if isinstance(first, dict) and any(k in first for k in ["rentalPrice", "listingId", "street", "id"]):
            return obj
    if isinstance(obj, dict):
        for val in obj.values():
            result = _find_listings_in_next_data(val, depth + 1)
            if result:
                return result
    return []
 
def check_kamernet(scraper):
    new_items = []
    print(f"\n[Kamernet] Fetching: {KAMERNET_URL}")
    res = scraper.get(KAMERNET_URL)
    print(f"[Kamernet] Status: {res.status_code}")
 
    if res.status_code != 200:
        print(f"[Kamernet] Blocked. Snippet:\n{res.text[:300]}")
        return new_items
 
    soup = BeautifulSoup(res.text, "html.parser")
    page_title = soup.title.string.strip() if soup.title else "N/A"
    print(f"[Kamernet] Page title: {page_title}")
 
    script_tag = soup.find("script", {"id": "__NEXT_DATA__"})
    if script_tag:
        try:
            data = json.loads(script_tag.string)
            listings_raw = _find_listings_in_next_data(data)
            print(f"[Kamernet] Found {len(listings_raw)} listings in __NEXT_DATA__.")
            for listing in listings_raw:
                listing_id = listing.get("id") or listing.get("listingId")
                if not listing_id:
                    continue
 
                title = listing.get("title") or listing.get("street") or "Room"
                price_val = listing.get("rentalPrice") or listing.get("price") or "?"
                price = f"EUR {price_val}/mo" if price_val != "?" else "Check listing"
 
                # Check city field if available
                city = str(listing.get("city") or listing.get("cityName") or "")
                if not is_eindhoven_only(city):
                    print(f"  [Kamernet] Skipped (not Eindhoven): {title} | {city}")
                    continue
 
                link = f"https://kamernet.nl/en/for-rent/room-eindhoven/room/{listing_id}"
                if link not in seen:
                    seen.add(link)
                    save_link(link)
                    new_items.append((title, price, link, "Kamernet"))
        except Exception as e:
            print(f"[Kamernet] Failed to parse __NEXT_DATA__: {e}")
    else:
        print("[Kamernet] No __NEXT_DATA__ found (JS-rendered). Trying link fallback...")
        listings = soup.select("a[href*='/for-rent/']")
        print(f"[Kamernet] Fallback found {len(listings)} links.")
        if len(listings) == 0:
            print("[Kamernet] DEBUG - HTML snippet (first 1500 chars):")
            print(res.text[:1500])
 
        for item in listings[:20]:
            href = item.get("href", "")
            if not href or "/room-eindhoven/" not in href:
                continue
            link = "https://kamernet.nl" + href if href.startswith("/") else href
            title = item.get_text(strip=True) or "Room"
            # Fallback links are already scoped to /room-eindhoven/ so no extra filter needed
            if link not in seen:
                seen.add(link)
                save_link(link)
                new_items.append((title, "Check listing", link, "Kamernet"))
 
    return new_items
 
# -------- MAIN --------
def main():
    print("=" * 50)
    print("Room Finder Bot v5 — Eindhoven only")
    print("=" * 50)
    send_test_message()
 
    print("\nInitializing scraper...")
    try:
        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "desktop": True}
        )
    except Exception as e:
        print(f"Failed to initialize scraper: {e}")
        sys.exit(1)
 
    found = []
    found += check_pararius(scraper)
    found += check_kamernet(scraper)
 
    print("\n" + "=" * 50)
    if found:
        print(f"{len(found)} new listing(s) found! Sending to Discord...")
        for title, price, link, source in found:
            print(f"  [{source}] {title} | {price}")
            send(title, price, link, source)
    else:
        print("No new listings found this cycle.")
 
if __name__ == "__main__":
    main()
