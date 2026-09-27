"""rss.json'u okur ve feeds tablosunu onunla eşitler."""
import logging
import unicodedata
from urllib.parse import urlparse

import httpx

from .db import DB, now

log = logging.getLogger(__name__)

# Bilinen yayın organlarının okunur adları; listede olmayanlar beslemenin kendi başlığıyla gösterilir.
NAMES = {
    "ntv.com.tr": "NTV", "sozcu.com.tr": "Sözcü", "hurriyet.com.tr": "Hürriyet",
    "haberturk.com": "Habertürk", "cnnturk.com": "CNN Türk", "trthaber.com": "TRT Haber",
    "onedio.com": "Onedio", "cnbce.com": "CNBC-e", "ajansspor.com": "Ajansspor",
    "kontraspor.com": "Kontraspor", "webtekno.com": "Webtekno", "12punto.com.tr": "12punto",
    "haberglobal.com": "Haber Global", "cumhuriyet.com.tr": "Cumhuriyet", "chip.com.tr": "CHIP",
    "donanimhaber.com": "DonanımHaber", "evrimagaci.org": "Evrim Ağacı", "hukukihaber.net": "Hukuki Haber",
    "son.tv": "Son TV", "nytimes.com": "New York Times", "theguardian.com": "The Guardian",
    "aljazeera.com": "Al Jazeera", "scmp.com": "South China Morning Post", "dailymail.com": "Daily Mail",
    "dailymail.co.uk": "Daily Mail", "nypost.com": "New York Post", "cbsnews.com": "CBS News",
    "bbc.co.uk": "BBC", "bbc.com": "BBC",
}


def domain_of(url: str) -> str:
    host = urlparse(url).hostname or ""
    for prefix in ("www.", "rss.", "feeds.", "m.", "amp."):
        if host.startswith(prefix):
            host = host[len(prefix):]
    return host


def source_name(url: str, feed_title: str | None = None) -> str:
    d = domain_of(url)
    if d == "bbc.com" and "/turkce" in url:
        return "BBC Türkçe"
    return NAMES.get(d) or (feed_title or d).strip()


def _fold(s: str) -> str:
    s = s.lower().replace("ı", "i")
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


# Tanımadığımız yeni kategori adları için anahtar kelime tahmini
GUESS = [
    ("spor", ("spor", "futbol", "basketbol")),
    ("ekonomi", ("ekonomi", "finans", "borsa", "piyasa", "is dunyasi", "para")),
    ("teknoloji", ("teknoloji", "bilim", "tech", "science")),
    ("dunya", ("dunya", "world", "global")),
    ("gundem", ("gundem", "siyaset", "politika", "hukuk", "adalet", "turkiye", "son dakika")),
]


def map_category(name: str, cfg) -> str | None:
    sc = cfg["sources"]
    if name in sc["category_map"]:
        return sc["category_map"][name]
    if name in sc["ignore"]:
        return None
    folded = _fold(name)
    for section, keys in GUESS:
        if any(k in folded for k in keys):
            log.info("Yeni kategori %r -> %s olarak eşlendi", name, section)
            return section
    log.warning("Yeni kategori %r tanınmadı, atlanıyor (config.yaml'a ekleyebilirsiniz)", name)
    return None


def refresh(db: DB, cfg, force: bool = False) -> None:
    from datetime import datetime, timedelta, timezone

    last = db.meta_get("sources_refreshed")
    due = not last or datetime.fromisoformat(last) < datetime.now(timezone.utc) - timedelta(
        minutes=cfg["sources"]["refresh_minutes"])
    if not (due or force):
        return

    data = None
    for url in (cfg["sources"]["url"], cfg["sources"]["fallback_url"]):
        try:
            r = httpx.get(url, timeout=20, follow_redirects=True, headers={"Cache-Control": "no-cache"})
            r.raise_for_status()
            data = r.json()
            break
        except Exception as e:  # noqa: BLE001
            log.warning("Kaynak listesi alınamadı (%s): %s", url, e)
    if data is None:
        return

    wanted: dict[str, tuple[str, str]] = {}
    for group in data:
        section = map_category(group["kategori"], cfg)
        if not section:
            continue
        for url in group["rss"]:
            wanted.setdefault(url.strip(), (group["kategori"], section))

    known = {r["url"]: r["active"] for r in db.q("SELECT url, active FROM feeds")}
    added = [u for u in wanted if u not in known]
    removed = [u for u, a in known.items() if a and u not in wanted]
    for url, (cat, section) in wanted.items():
        db.x("""INSERT INTO feeds(url, category, section) VALUES (?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET category=excluded.category, section=excluded.section, active=1""",
             url, cat, section)
    for url in removed:
        db.x("UPDATE feeds SET active=0 WHERE url=?", url)
    db.commit()
    db.meta_set("sources_refreshed", now())
    if added or removed:
        log.info("Kaynaklar güncellendi: +%d yeni, -%d kaldırıldı, toplam %d", len(added), len(removed), len(wanted))
