import os
import time
import feedparser
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

RSS_URL = "https://news.google.com/rss/search?q=Elaz%C4%B1%C4%9F&hl=tr&gl=TR&ceid=TR:tr"

seen_links = set()

def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": text
    })

def check_news():
    feed = feedparser.parse(RSS_URL)

    for entry in reversed(feed.entries[:20]):
        if entry.link not in seen_links:
            seen_links.add(entry.link)
            send_message(f"📰 {entry.title}\n{entry.link}")

send_message("✅ Bot çalışıyor")

while True:
    try:
        check_news()
    except:
        pass

    time.sleep(60)