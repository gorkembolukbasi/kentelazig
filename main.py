import os
import time
import html
import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

KEYWORDS = ["elazığ", "elazig", "elazığ’da", "elazigda", "elazığda"]

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


def keyword_var_mi(text):
    text = (text or "").lower()
    return any(keyword in text for keyword in KEYWORDS)


def get_page_details(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8"
        }

        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        image_url = None

        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            image_url = og_image["content"]

        if not image_url:
            twitter_image = soup.find("meta", attrs={"name": "twitter:image"})
            if twitter_image and twitter_image.get("content"):
                image_url = twitter_image["content"]

        content = ""

        og_desc = soup.find("meta", property="og:description")
        if og_desc and og_desc.get("content"):
            content += og_desc["content"] + " "

        desc = soup.find("meta", attrs={"name": "description"})
        if desc and desc.get("content"):
            content += desc["content"] + " "

        paragraphs = soup.find_all("p")
        paragraph_text = " ".join(p.get_text(" ", strip=True) for p in paragraphs[:10])
        content += paragraph_text

        content = clean_text(content)
        content = content[:1200]

        return content, image_url

    except Exception as e:
        print("Detay sayfa hatası:", url, e)
        return "", None


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
        print("Mesaj gönderme hatası:", e)


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
        print("Foto gönderme hatası:", e)
        send_text(caption)


def send_news_message(message, image_url=None):
    if image_url:
        send_photo(message, image_url)
    else:
        send_text(message)


def check_news():
    global last_check_time
    last_check_time = turkiye_saati()

    for rss in RSS_FEEDS:
        try:
            feed = feedparser.parse(rss)

            for entry in reversed(feed.entries[:30]):
                title = clean_text(entry.get("title", ""))
                summary = clean_text(entry.get("summary", ""))
                link = entry.get("link", "")

                if not link or link in seen_links:
                    continue

                content, image_url = get_page_details(link)

                search_area = f"{title} {summary} {content}"

                if not keyword_var_mi(search_area):
                    continue

                seen_links.add(link)

                source = feed.feed.get("title", "Bilinmiyor")
                published = entry.get("published", "Tarih bilgisi yok")

                final_content = content if content else summary
                if not final_content:
                    final_content = "İçerik alınamadı."

                message = f"""
📰 <b>Kent Elazığ Haber</b>

<b>Haber Başlığı:</b> {html.escape(title)}

<b>İçerik:</b> {html.escape(final_content)}

<b>Yayınlayıcı:</b> {html.escape(source)}
<b>Link:</b> {html.escape(link)}

<b>Yayınlanma Tarihi:</b> {html.escape(published)}
"""

                send_news_message(message, image_url)

        except Exception as e:
            print("RSS kontrol hatası:", rss, e)


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
                durum_mesaji = f"""
🤖 <b>Bot Durumu</b>

Durum: Aktif ✅
Son kontrol: {last_check_time}
Toplam kaynak: {len(RSS_FEEDS)}
Toplanan haber: {len(seen_links)}
"""
                send_text(durum_mesaji)

    except Exception as e:
        print("Komut kontrol hatası:", e)


while True:
    check_news()
    handle_commands()
    time.sleep(60)