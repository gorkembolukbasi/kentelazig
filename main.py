import os
import time
import html
import feedparser
import requests
from datetime import datetime, timedelta

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

KEYWORDS = ["elazığ", "elazig"]

RSS_FEEDS = [
    "https://rss.haberler.com/RssNew.aspx",
    "https://rss.haberler.com/",

    "https://www.trthaber.com/sondakika_articles.rss",
    "https://www.trthaber.com/gundem_articles.rss",
    "https://www.trthaber.com/turkiye_articles.rss",

    "https://www.sondakika.com/elazig/rss/",
    "https://www.bursasaati.com.tr/rss",

    "https://www.haberturk.com/rss",
    "https://haberglobal.com.tr/rss",
    "https://www.ntv.com.tr/turkiye.rss",
    "https://www.ntv.com.tr/gundem.rss",

    "https://www.cnnturk.com/feed/rss/turkiye/news",
    "https://www.milliyet.com.tr/rss/rssNew/turkiye.xml",
    "https://www.aksam.com.tr/rss/rss.asp",
    "https://www.yeniakit.com.tr/rss",
    "https://www.takvim.com.tr/rss",
    "https://www.sabah.com.tr/rss/anasayfa.xml"
]

seen_links = set()
last_check_time = "Henüz kontrol yapılmadı"
last_update_id = None


def turkiye_saati():
    return (datetime.utcnow() + timedelta(hours=3)).strftime("%d.%m.%Y %H:%M:%S")


def keyword_var_mi(text):
    text = (text or "").lower()
    return any(k in text for k in KEYWORDS)


def send_text(text):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }, timeout=10)
    except Exception as e:
        print("Mesaj hatası:", e)


def send_photo(caption, image_url):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        response = requests.post(url, data={
            "chat_id": CHAT_ID,
            "photo": image_url,
            "caption": caption,
            "parse_mode": "HTML"
        }, timeout=10)

        if response.status_code != 200:
            send_text(caption)

    except Exception as e:
        print("Foto hatası:", e)
        send_text(caption)


def get_image(entry):
    try:
        if "media_content" in entry:
            return entry.media_content[0].get("url")

        if "media_thumbnail" in entry:
            return entry.media_thumbnail[0].get("url")

        if "enclosures" in entry:
            return entry.enclosures[0].get("href")
    except:
        pass

    return None


def check_news():
    global last_check_time
    last_check_time = turkiye_saati()

    for rss in RSS_FEEDS:
        try:
            feed = feedparser.parse(rss)

            for entry in reversed(feed.entries[:40]):
                title = entry.get("title", "")
                summary = entry.get("summary", "")
                link = entry.get("link", "")

                if not link or link in seen_links:
                    continue

                search_area = f"{title} {summary}"

                if not keyword_var_mi(search_area):
                    continue

                seen_links.add(link)

                source = feed.feed.get("title", "Bilinmiyor")
                published = entry.get("published", "Tarih bilgisi yok")
                content = summary if summary else "İçerik bulunamadı."
                image_url = get_image(entry)

                message = f"""
📰 <b>Kent Elazığ Haber</b>

<b>Haber Başlığı:</b> {html.escape(title)}

<b>İçerik:</b> {html.escape(content)}

<b>Yayınlayıcı:</b> {html.escape(source)}
<b>Link:</b> {html.escape(link)}

<b>Yayınlanma Tarihi:</b> {html.escape(published)}
"""

                if image_url:
                    send_photo(message, image_url)
                else:
                    send_text(message)

        except Exception as e:
            print("RSS hata:", rss, e)


def handle_commands():
    global last_update_id

    try:
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
                send_text(f"""
🤖 <b>Bot Durumu</b>

Durum: Aktif ✅
Son kontrol: {last_check_time}
Toplam kaynak: {len(RSS_FEEDS)}
""")

    except Exception as e:
        print("Komut hatası:", e)


while True:
    try:
        check_news()
        handle_commands()
    except Exception as e:
        print("GENEL HATA:", e)

    time.sleep(60)