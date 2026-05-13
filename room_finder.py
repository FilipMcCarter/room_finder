import requests
from bs4 import BeautifulSoup
import time

# -------- CONFIG --------
PARARIUS_URL = "https://www.pararius.com/rooms/eindhoven/0-800"
KAMERNET_URL = "https://kamernet.nl/en/for-rent/rooms-eindhoven"

DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1504047942401790012/YJV4UgJRrXh_ah90e4cBNGn5JNatOWAV0Dho5k5GRXZKjNEw8XSEHCCBDwdOWUjxzwda"  # <-- PUT YOUR WEBHOOK HERE

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

seen = set()

# -------- DISCORD SEND --------
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

        # optional keyword filter (keeps rooms/studios relevant)
        if not any(k in title.lower() for k in ["room", "studio", "kamer"]):
            continue

        if link not in seen:
            seen.add(link)
            new_items.append((title, price, link, "Pararius"))

    return new_items

# -------- KAMERNET --------
def check_kamernet():
    new_items = []
    res = requests.get(KAMERNET_URL, headers=HEADERS)
    soup = BeautifulSoup(res.text, "html.parser")

    listings = soup.select("a[href*='/details/']")

    for item in listings[:10]:  # limit noise
        link = "https://kamernet.nl" + item["href"]
        title = item.get_text(strip=True)

        # basic filter
        if not any(k in title.lower() for k in ["room", "studio", "kamer"]):
            continue

        price = "Check listing"

        if link not in seen:
            seen.add(link)
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
                time.sleep(1)  # avoid spam bursts

        else:
            print("No new listings")

    except Exception as e:
        print("Error:", e)
    requests.post(DISCORD_WEBHOOK, json={"content": "Bot test message"})
    time.sleep(180)  # check every 3 minutes
