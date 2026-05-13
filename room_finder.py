#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
import time
import os
#we act as a web service to get the free tier functional 
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

DISCORD_WEBHOOK = "https://discord.com/api/webhooks/XXXXX/YYYYY"  # <-- PUT YOUR WEBHOOK

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

SEEN_FILE = "seen_links.txt"

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
    msg = f"**{source}**\n{title}\n💶 {price}\n{link}"
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": msg})
    except Exception as e:
        print("Discord error:", e)

# -------- PARARIUS --------
def check_pararius():
    new_items = []
    res = requests.get(PARARIUS_URL, headers=HEADERS)
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
    res = requests.get(KAMERNET_URL, headers=HEADERS)
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
                print(f"[{source}] {title} | {price}")
                print(link)
                print("-" * 40)

                send(title, price, link, source)
                time.sleep(1)
        else:
            print("No new listings")

    except Exception as e:
        print("Error:", e)

    time.sleep(180)
