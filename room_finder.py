import os
import requests
import cloudscraper
from bs4 import BeautifulSoup
import sys

# -------- CONFIG --------
PARARIUS_URL = "https://www.pararius.com/rooms/eindhoven/0-800"
KAMERNET_URL = "https://kamernet.nl/en/for-rent/rooms-eindhoven"

# Pull webhook securely from GitHub Secrets
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK")
if not DISCORD_WEBHOOK:
    print("Error: DISCORD_WEBHOOK environment variable not set.")
    sys.exit(1)

SEEN_FILE = "seen_links.txt"

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
            print(f"Successfully sent to Discord: {title}")
        else:
            print(f"Discord error: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"Discord exception: {e}")
def send_test_message():
    try:
        msg = "Bot successfully started on Render! (v2)"
        res = requests.post(DISCORD_WEBHOOK, json={"content": msg})
        if res.status_code == 204:
            print("Test message successfully sent to Discord.", flush=True)
        else:
            print(f"Failed to send test message. Status: {res.status_code}", flush=True)
    except Exception as e:
        print(f"Test message exception: {e}", flush=True)
# -------- PARARIUS --------
def check_pararius(scraper):
    new_items = []
    print("Checking Pararius...")
    res = scraper.get(PARARIUS_URL)
    
    if res.status_code != 200:
        print(f"Pararius blocked the request! Status Code: {res.status_code}")
        return new_items

    soup = BeautifulSoup(res.text, "html.parser")
    listings = soup.select(".listing-search-item")

    for item in listings:
        title_tag = item.select_one(".listing-search-item__link--title")
        price_tag = item.select_one(".listing-search-item__price")

        if not title_tag or not price_tag:
            continue

        link = "https://www.pararius.com" + title_tag["href"]
        title = title_tag.get_text(strip=True)
        price = price_tag.get_text(strip=True)

        if not any(k in title.lower() for k in ["room", "studio", "kamer"]):
            continue

        if link not in seen:
            seen.add(link)
            save_link(link)
            new_items.append((title, price, link, "Pararius"))

    return new_items

# -------- KAMERNET --------
def check_kamernet(scraper):
    new_items = []
    print("Checking Kamernet...")
    res = scraper.get(KAMERNET_URL)
    
    if res.status_code != 200:
        print(f"Kamernet blocked the request! Status Code: {res.status_code}")
        return new_items

    soup = BeautifulSoup(res.text, "html.parser")
    listings = soup.select("a[href*='/details/']")

    for item in listings[:10]:
        link = "https://kamernet.nl" + item["href"]
        title = item.get_text(strip=True)

        if not any(k in title.lower() for k in ["room", "studio", "kamer"]):
            continue

        price = "Check listing"

        if link not in seen:
            seen.add(link)
            save_link(link)
            new_items.append((title, price, link, "Kamernet"))

    return new_items

# -------- MAIN EXECUTION --------
def main():
    print("Bot script initialized. Sending test message...", flush=True)
    send_test_message()
    print("Initializing scraper...")
    try:
        scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
    except Exception as e:
        print(f"Failed to initialize scraper: {e}")
        sys.exit(1)

    found = []
    found += check_pararius(scraper)
    found += check_kamernet(scraper)

    if found:
        for title, price, link, source in found:
            print(f"Found [{source}] {title} | {price}")
            send(title, price, link, source)
    else:
        print("No new listings found this cycle.")

if __name__ == "__main__":
    main()
