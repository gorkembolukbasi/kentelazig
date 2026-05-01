import os
import time
import html
import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

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
last_check_time = "Henüz kontrol yapılmadı"
last_update_id = None


def turkiye_saati():
    return (datetime.utcnow() + timedelta(hours=3)).strftime("%d.%m.%Y %H:%M:%S")


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

        image_url = None
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            image_url = og_image["content"]

        paragraphs = soup.find_all("p")
        content = " ".join(p.get_text(" ", strip=True) for p in paragraphs[:5])
        content = content[:900]

        return content, image_url
    except:
        return "", None


def send_text(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    })


def send_photo(caption, image_url):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    requests.post(url, data={
        "chat_id": CHAT_ID,
        "photo": image_url,
        "caption": caption,
        "parse_mode": "HTML"
    })


def send_news_message(message, image_url=None):
    if image_url:
        send_photo(message, image_url)
    else:
        send_text(message)


def check_news():
    global last_check_time
    last_check_time = turkiye_saati()

    for rss in RSS_FEEDS:
        feed = feedparser.parse(rss)

        for entry in reversed(feed.entries[:20]):
            title = clean_text(entry.get("title", ""))
            summary = clean_text(entry.get("summary", ""))
            link = entry.get("link", "")

            search_area = f"{title} {summary}".lower()

            if KEYWORD not in search_area and "elazig" not in search_area:
                continue

            if not link or link in seen_links:
                continue

            seen_links.add(link)

            source = feed.feed.get("title", "Bilinmiyor")
            published = entry.get("published", "Tarih bilgisi yok")

            content, image_url = get_page_details(link)

            if not content:
                content = summary if summary else "İçerik alınamadı."

            message = f"""
📰 <b>Kent Elazığ Haber</b>

<b>Haber Başlığı:</b> {html.escape(title)}

<b>İçerik:</b> {html.escape(content)}

<b>Yayınlayıcı:</b> {html.escape(source)}
<b>Link:</b> {html.escape(link)}

<b>Yayınlanma Tarihi:</b> {html.escape(published)}
"""

            send_news_message(message, image_url)


def handle_commands():
    global last_update_id

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"

    params = {}
    if last_update_id is not None:
        params["offset"] = last_update_id + 1

    res = requests.get(url, params=params, timeout=10).json()

    for update in res.get("result", []):
        last_update_id = update["update_id"]

        message = update.get("message", {})
        text = message.get("text", "")

        if text.startswith("/durum"):
            durum_mesaji = f"""
🤖 <b>Bot Durumu</b>

Durum: Aktif ✅
Son kontrol: {last_check_time}
Toplam kaynak: {len(RSS_FEEDS)}
Toplanan haber: {len(seen_links)}
"""
            send_text(durum_mesaji)


while True:
    try:
        check_news()
        handle_commands()
    except Exception as e:
        send_text(f"⚠️ Hata: {html.escape(str(e))}")

    time.sleep(60)