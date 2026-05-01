import os
import time
import html
import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

KEYWORD = "elazığ"

RSS_FEEDS = [
    "https://rss.haberler.com/",
    "https://www.iha.com.tr/rss",
    "https://www.ensonhaber.com/rss/ensonhaber.xml",
    "https://www.sozcu.com.tr/feeds-son-dakika",
    "https://www.hurriyet.com.tr/rss/anasayfa",
    "https://www.haberturk.com/rss/anasayfa",
    "https://www.trthaber.com/sondakika_articles.rss",
    "https://www.bursasaati.com.tr/rss",
    "https://www.sondakika.com/elazig/rss/"
]

seen_links = set()


def clean_text(text):
    if not text:
        return ""
    soup = BeautifulSoup(text, "html.parser")
    return soup.get_text(" ", strip=True)


def get_page_details(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        image = None
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            image = og_image["content"]

        paragraphs = soup.find_all("p")
        content = " ".join(p.get_text(" ", strip=True) for p in paragraphs[:5])
        content = content[:900]

        return content, image
    except:
        return "", None


def send_message(text, image_url=None):
    if image_url:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        requests.post(url, data={
            "chat_id": CHAT_ID,
            "photo": image_url,
            "caption": text,
            "parse_mode": "HTML"
        })
    else:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        })


def check_news():
    for rss in RSS_FEEDS:
        feed = feedparser.parse(rss)

        for entry in reversed(feed.entries[:20]):
            title = clean_text(entry.get("title", ""))
            summary = clean_text(entry.get("summary", ""))
            link = entry.get("link", "")

            search_area = f"{title} {summary}".lower()

            if KEYWORD not in search_area and "elazig" not in search_area:
                continue

            if link in seen_links:
                continue

            seen_links.add(link)

            source = feed.feed.get("title", "Bilinmiyor")
            published = entry.get("published", "Tarih bilgisi yok")

            content, image_url = get_page_details(link)

            if not content:
                content = summary if summary else "İçerik alınamadı."

            message = f"""
<b>Haber Başlığı;</b> {html.escape(title)}

<b>İçerik;</b> {html.escape(content)}

<b>Yayınlayıcı;</b> {html.escape(source)}
<b>Link;</b> {html.escape(link)}

<b>Yayınlanma Tarihi;</b> {html.escape(published)}
"""

            send_message(message, image_url)


send_message("✅ Kent Elazığ botu çalışıyor.")

while True:
    try:
        check_news()
    except Exception as e:
        send_message(f"⚠️ Bot hata aldı: {html.escape(str(e))}")

    time.sleep(60)