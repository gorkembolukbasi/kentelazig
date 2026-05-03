import os
import time
import html
import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

KEYWORDS = ["elazığ", "elazig"]

RSS_FEEDS = [
    "https://news.google.com/rss/search?q=Elaz%C4%B1%C4%9F&hl=tr&gl=TR&ceid=TR:tr",
    "https://rss.haberler.com/RssNew.aspx",
    "https://www.iha.com.tr/rss",
    "https://www.ensonhaber.com/rss/ensonhaber.xml",
    "https://www.sozcu.com.tr/feeds-son-dakika",
    "https://www.hurriyet.com.tr/rss/anasayfa",
    "https://www.haberturk.com/rss",
    "https://www.trthaber.com/sondakika_articles.rss",
    "https://www.bursasaati.com.tr/rss",
    "https://www.sondakika.com/elazig/rss/"
]

seen_links = set()
seen_titles = {}

TTL_MINUTES = 120  # 2 saat

last_check_time = "Henüz çalışmadı"


def turkiye_saati():
    return (datetime.utcnow() + timedelta(hours=3)).strftime("%d.%m.%Y %H:%M:%S")


def temizle_title(title):
    return title.lower().replace(" ", "").replace("-", "").replace("'", "")


def keyword_var_mi(text):
    text = (text or "").lower()
    return any(k in text for k in KEYWORDS)


def temizle_eski_basliklar():
    now = datetime.utcnow()
    silinecek = []

    for key, zaman in seen_titles.items():
        if now - zaman > timedelta(minutes=TTL_MINUTES):
            silinecek.append(key)

    for key in silinecek:
        del seen_titles[key]


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
        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            image = og["content"]

        paragraphs = soup.find_all("p")
        content = " ".join(p.text for p in paragraphs[:6])

        return content, image

    except:
        return "", None


def send_text(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    })


def send_photo(caption, image):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    requests.post(url, data={
        "chat_id": CHAT_ID,
        "photo": image,
        "caption": caption,
        "parse_mode": "HTML"
    })


def check_news():
    global last_check_time

    temizle_eski_basliklar()
    last_check_time = turkiye_saati()

    for rss in RSS_FEEDS:
        feed = feedparser.parse(rss)

        for entry in reversed(feed.entries[:30]):
            title = clean_text(entry.get("title", ""))
            summary = clean_text(entry.get("summary", ""))
            link = entry.get("link", "")

            if not link or link in seen_links:
                continue

            title_key = temizle_title(title)

            if title_key in seen_titles:
                continue

            content, image = get_page_details(link)

            search_area = f"{title} {summary} {content}"

            if not keyword_var_mi(search_area):
                continue

            seen_links.add(link)
            seen_titles[title_key] = datetime.utcnow()

            source = feed.feed.get("title", "Bilinmiyor")
            published = entry.get("published", "Tarih yok")

            final_content = content if content else summary

            message = f"""
📰 <b>Kent Elazığ Haber</b>

<b>Başlık:</b> {html.escape(title)}

<b>İçerik:</b> {html.escape(final_content)}

<b>Kaynak:</b> {html.escape(source)}
<b>Link:</b> {html.escape(link)}

<b>Tarih:</b> {html.escape(published)}
"""

            if image:
                send_photo(message, image)
            else:
                send_text(message)


def handle_commands():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    res = requests.get(url).json()

    if not res["result"]:
        return

    last_msg = res["result"][-1]
    text = last_msg.get("message", {}).get("text", "")

    if text.startswith("/durum"):
        send_text(f"""
🤖 <b>Bot Durumu</b>

Durum: Aktif
Son kontrol: {last_check_time}
Toplam kaynak: {len(RSS_FEEDS)}
""")


while True:
    try:
        check_news()
        handle_commands()
    except Exception as e:
        print("HATA:", e)

    time.sleep(60)