#!/usr/bin/env python3

import os
# Force Python to print logs immediately in Render
os.environ["PYTHONUNBUFFERED"] = "1"

import requests
import cloudscraper
from bs4 import BeautifulSoup
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")

def run_server():
    server = HTTPServer(("0.0.0.0", 10000), DummyHandler)
    server.serve_forever()

threading.Thread(target=run_server, daemon=True).start()

# -------- CONFIG --------
PARARIUS_URL = "https://www.pararius.com/rooms/eindhoven/0-800"
KAMERNET_URL = "https://kamernet.nl/en/for-rent/rooms-eindhoven"

DISCORD_WEBHOOK = "https://discord.com/api/webhooks/XXXXX/YYYYY"  # <-- MAKE SURE THIS IS YOUR REAL WEBHOOK

SEEN_FILE = "seen_links.txt"

# Create a scraper that bypasses basic Cloudflare/bot protections
scraper = cloudscraper.create_scraper(browser={
    'browser': 'chrome',
    'platform': 'windows',
    'desktop': True
})

# -------- LOAD SEEN --------
if os.path.exists(SEEN_FILE):
    with open(SEEN_FILE, "r") as f:
        seen = set(line.strip() for line in f)
else:
    seen = set()

# -------- SAVE LINK --------
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

# -------- PARARIUS --------
def check_pararius():
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
def check_kamernet():
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

# -------- MAIN LOOP --------
print("Bot started...")

while True:
    try:
        found = []

        found += check_pararius()
        time.sleep(2)
        found += check_kamernet()

        if found:
            for title, price, link, source in found:
                print(f"Found [{source}] {title} | {price}")
                send(title, price, link, source)
                time.sleep(1)
        else:
            print("No new listings found this cycle.")

    except Exception as e:
        print(f"Major Error: {e}")

    time.sleep(180)
