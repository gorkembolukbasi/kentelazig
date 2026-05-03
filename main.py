import os
import time
import html
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

import feedparser
import requests
from bs4 import BeautifulSoup

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

KEYWORDS = ["elazığ", "elazig", "elazığda", "elazigda", "elazığ'da", "elazig'da"]

RSS_FEEDS = [
    "https://news.google.com/rss/search?q=Elaz%C4%B1%C4%9F&hl=tr&gl=TR&ceid=TR:tr",
    "https://rss.haberler.com/RssNew.aspx",
    "https://www.iha.com.tr/rss",
    "https://www.ensonhaber.com/rss/ensonhaber.xml",
    "https://www.sozcu.com.tr/feeds-son-dakika",
    "https://www.hurriyet.com.tr/rss/anasayfa",
    "https://www.haberturk.com/rss",
    "https://www.trthaber.com/sondakika_articles.rss",
    "https://www.trthaber.com/gundem_articles.rss",
    "https://www.bursasaati.com.tr/rss",
    "https://www.sondakika.com/elazig/rss/"
]

CHECK_SECONDS = 60
TITLE_TTL_MINUTES = 120

seen_links = set()
seen_titles = {}
last_check_time = "Henüz kontrol yapılmadı"
last_update_id = None


def now_utc():
    return datetime.now(timezone.utc)


def turkiye_saati():
    return now_utc().astimezone(timezone(timedelta(hours=3))).strftime("%d.%m.%Y %H:%M:%S")


def clean_text(text):
    if not text:
        return ""
    text = BeautifulSoup(str(text), "html.parser").get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_title(title):
    title = clean_text(title).lower()
    title = title.replace("ı", "i").replace("ğ", "g").replace("ü", "u").replace("ş", "s").replace("ö", "o").replace("ç", "c")
    title = re.sub(r"[^a-z0-9]", "", title)
    return title


def keyword_var_mi(text):
    text = clean_text(text).lower()
    return any(k in text for k in KEYWORDS)


def temizle_eski_basliklar():
    limit = now_utc() - timedelta(minutes=TITLE_TTL_MINUTES)
    for key in list(seen_titles.keys()):
        if seen_titles[key] < limit:
            del seen_titles[key]


def get_image_from_entry(entry):
    try:
        if "media_content" in entry:
            for media in entry.media_content:
                if media.get("url"):
                    return media.get("url")

        if "media_thumbnail" in entry:
            for media in entry.media_thumbnail:
                if media.get("url"):
                    return media.get("url")

        if "enclosures" in entry:
            for enc in entry.enclosures:
                href = enc.get("href")
                enc_type = enc.get("type", "")
                if href and "image" in enc_type:
                    return href
    except Exception:
        pass

    return None


def get_page_details(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
            "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8"
        }

        r = requests.get(url, headers=headers, timeout=12, allow_redirects=True)
        final_url = r.url
        soup = BeautifulSoup(r.text, "html.parser")

        image_url = None

        image_selectors = [
            ("meta", {"property": "og:image"}, "content"),
            ("meta", {"property": "og:image:secure_url"}, "content"),
            ("meta", {"name": "twitter:image"}, "content"),
            ("meta", {"name": "twitter:image:src"}, "content"),
        ]

        for tag_name, attrs, field in image_selectors:
            tag = soup.find(tag_name, attrs=attrs)
            if tag and tag.get(field):
                image_url = urljoin(final_url, tag.get(field))
                break

        if not image_url:
            img = soup.find("img")
            if img:
                src = img.get("src") or img.get("data-src") or img.get("data-original")
                if src:
                    image_url = urljoin(final_url, src)

        content_parts = []

        for selector in [
            ("meta", {"property": "og:description"}, "content"),
            ("meta", {"name": "description"}, "content"),
            ("meta", {"name": "twitter:description"}, "content"),
        ]:
            tag = soup.find(selector[0], attrs=selector[1])
            if tag and tag.get(selector[2]):
                content_parts.append(tag.get(selector[2]))

        paragraphs = soup.find_all("p")
        for p in paragraphs[:12]:
            txt = p.get_text(" ", strip=True)
            if txt and len(txt) > 20:
                content_parts.append(txt)

        content = clean_text(" ".join(content_parts))
        content = content[:1100]

        return content, image_url

    except Exception as e:
        print("Detay sayfa hatası:", url, e)
        return "", None


def send_text(text):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={
            "chat_id": CHAT_ID,
            "text": text[:3900],
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }, timeout=12)
    except Exception as e:
        print("Mesaj gönderme hatası:", e)


def send_photo(caption, image_url):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"

        response = requests.post(url, data={
            "chat_id": CHAT_ID,
            "photo": image_url,
            "caption": caption[:1000],
            "parse_mode": "HTML"
        }, timeout=15)

        if response.status_code != 200:
            print("Foto gönderilemedi:", response.text)
            send_text(caption)

    except Exception as e:
        print("Foto gönderme hatası:", e)
        send_text(caption)


def check_news():
    global last_check_time

    temizle_eski_basliklar()
    last_check_time = turkiye_saati()

    for rss in RSS_FEEDS:
        try:
            feed = feedparser.parse(rss)

            for entry in reversed(feed.entries[:40]):
                title = clean_text(entry.get("title", ""))
                summary = clean_text(entry.get("summary", ""))
                link = entry.get("link", "")

                if not title or not link:
                    continue

                title_key = normalize_title(title)

                if link in seen_links:
                    continue

                if title_key in seen_titles:
                    continue

                entry_image = get_image_from_entry(entry)

                content, page_image = get_page_details(link)
                image_url = page_image or entry_image

                search_area = f"{title} {summary} {content}"

                if not keyword_var_mi(search_area):
                    continue

                seen_links.add(link)
                seen_titles[title_key] = now_utc()

                source = clean_text(feed.feed.get("title", "Bilinmiyor"))
                published = clean_text(entry.get("published", "Tarih bilgisi yok"))

                final_content = content or summary or "İçerik alınamadı."
                final_content = final_content[:900]

                message = f"""
📰 <b>Kent Elazığ Haber</b>

<b>Haber Başlığı:</b> {html.escape(title)}

<b>İçerik:</b> {html.escape(final_content)}

<b>Yayınlayıcı:</b> {html.escape(source)}
<b>Link:</b> {html.escape(link)}

<b>Yayınlanma Tarihi:</b> {html.escape(published)}
"""

                if image_url:
                    send_photo(message, image_url)
                else:
                    send_text(message)

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
            last_update_id = update.get("update_id", last_update_id)

            message = update.get("message", {})
            text = message.get("text", "")

            if text.startswith("/durum"):
                durum_mesaji = f"""
🤖 <b>Bot Durumu</b>

Durum: Aktif ✅
Son kontrol: {last_check_time}
Toplam kaynak: {len(RSS_FEEDS)}
Tekrar engeli: {TITLE_TTL_MINUTES} dakika
"""
                send_text(durum_mesaji)

    except Exception as e:
        print("Komut kontrol hatası:", e)


while True:
    try:
        check_news()
        handle_commands()
    except Exception as e:
        print("Genel hata:", e)

    time.sleep(CHECK_SECONDS)