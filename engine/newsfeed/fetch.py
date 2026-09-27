"""RSS beslemelerini ve haber metinlerini çeker."""
import asyncio
import calendar
import hashlib
import html
import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import feedparser
import httpx
import trafilatura

from .db import DB, now
from .sources import domain_of, source_name

log = logging.getLogger(__name__)

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
TRACKING = re.compile(r"^(utm_|fbclid|gclid|ref$|ref_|cmpid|ito$|at_)")
BOILERPLATE = re.compile(r"\s*(Detaylar haberimizde|Haberin detayları için tıklayın|devamı için tıklayın|Continue reading|Read more)\.*…?\s*$", re.I)


def normalize_url(url: str) -> str:
    p = urlparse(url.strip())
    query = urlencode([(k, v) for k, v in parse_qsl(p.query) if not TRACKING.match(k)])
    return urlunparse((p.scheme or "https", p.netloc.lower(), p.path, "", query, ""))


def article_id(url: str) -> str:
    return hashlib.sha1(normalize_url(url).encode()).hexdigest()[:16]


def clean_text(s: str | None) -> str:
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(html.unescape(s))
    s = re.sub(r"\s+", " ", s).strip()
    return BOILERPLATE.sub("", s)


def entry_time(e) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        t = e.get(key)
        if t:
            return datetime.fromtimestamp(calendar.timegm(t), tz=timezone.utc)
    return None


async def _fetch_feed(client: httpx.AsyncClient, feed) -> tuple:
    headers = {}
    if feed["etag"]:
        headers["If-None-Match"] = feed["etag"]
    if feed["last_modified"]:
        headers["If-Modified-Since"] = feed["last_modified"]
    try:
        r = await client.get(feed["url"], headers=headers)
        if r.status_code == 304:
            return feed, None, r, None
        r.raise_for_status()
        return feed, feedparser.parse(r.content), r, None
    except Exception as e:  # noqa: BLE001
        return feed, None, None, f"{type(e).__name__}: {e}"[:200]


async def fetch_feeds(db: DB, cfg) -> int:
    t_now = datetime.now(timezone.utc)
    feeds = db.q("SELECT * FROM feeds WHERE active=1 AND (next_try IS NULL OR next_try <= ?)", t_now.isoformat())
    max_age = t_now - timedelta(hours=cfg["pipeline"]["max_item_age_hours"])
    async with httpx.AsyncClient(headers={"User-Agent": UA}, timeout=25, follow_redirects=True,
                                 limits=httpx.Limits(max_connections=cfg["pipeline"]["fetch_concurrency"] * 2)) as client:
        results = await asyncio.gather(*[_fetch_feed(client, f) for f in feeds])

    new = 0
    for feed, parsed, resp, err in results:
        if err:
            fails = feed["fail_count"] + 1
            # art arda hata veren besleme için bekleme süresi uzar (en fazla 6 saat)
            wait = min(15 * 2 ** (fails - 1), 360)
            db.x("UPDATE feeds SET last_error=?, fail_count=?, next_try=? WHERE url=?",
                 err, fails, (t_now + timedelta(minutes=wait)).isoformat(), feed["url"])
            continue
        db.x("UPDATE feeds SET last_ok=?, last_error=NULL, fail_count=0, next_try=NULL, etag=?, last_modified=? WHERE url=?",
             now(), resp.headers.get("etag"), resp.headers.get("last-modified"), feed["url"])
        if parsed is None:
            continue
        ftitle = clean_text(parsed.feed.get("title"))
        db.x("UPDATE feeds SET title=?, item_count=? WHERE url=?", ftitle, len(parsed.entries), feed["url"])
        for e in parsed.entries:
            link, title = e.get("link"), clean_text(e.get("title"))
            if not link or not title:
                continue
            aid = article_id(link)
            if db.one("SELECT 1 FROM articles WHERE id=?", aid):
                continue
            published = entry_time(e) or t_now
            if published > t_now + timedelta(hours=1):
                published = t_now
            if published < max_age:
                continue
            dom = domain_of(link)
            # aynı sitenin farklı adresle iki beslemede yayınladığı aynı haber
            if db.one("SELECT 1 FROM articles WHERE domain=? AND title=? AND published > ?",
                      dom, title, max_age.isoformat()):
                continue
            desc = clean_text(e.get("summary") or e.get("description"))
            if desc.startswith(title):
                desc = desc[len(title):].strip(" -–:")
            db.x("""INSERT INTO articles(id, url, title, description, source, domain, feed_url, section_hint, published, seen_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?)""",
                 aid, normalize_url(link), title, desc[:1500], source_name(link, ftitle), dom, feed["url"],
                 feed["section"], published.isoformat(timespec="seconds"), now())
            new += 1
    db.commit()
    ok = sum(1 for r in results if not r[3])
    log.info("Beslemeler: %d/%d başarılı, %d yeni haber", ok, len(results), new)
    return new


async def _fetch_body(client, sems, row) -> tuple[str, str | None]:
    async with sems[row["domain"]]:
        try:
            r = await client.get(row["url"])
            if r.status_code != 200:
                return row["id"], None
            text = await asyncio.to_thread(trafilatura.extract, r.text, favor_precision=True, include_comments=False)
            return row["id"], text
        except Exception:  # noqa: BLE001
            return row["id"], None


async def fetch_bodies(db: DB, cfg, ids: list[str]) -> None:
    rows = db.q(f"SELECT id, url, domain FROM articles WHERE body_status IS NULL AND id IN ({','.join('?' * len(ids))})", *ids)
    if not rows:
        return
    sems = defaultdict(lambda: asyncio.Semaphore(cfg["pipeline"]["per_host_concurrency"]))
    async with httpx.AsyncClient(headers={"User-Agent": UA}, timeout=20, follow_redirects=True) as client:
        results = await asyncio.gather(*[_fetch_body(client, sems, r) for r in rows])
    for aid, text in results:
        good = text and len(text) > 200
        db.x("UPDATE articles SET body=?, body_status=? WHERE id=?", text if good else None, "ok" if good else "fail", aid)
    db.commit()
