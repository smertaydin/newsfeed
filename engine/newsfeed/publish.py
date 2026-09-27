"""Veriyi JSON ve RSS olarak dışa aktarır, GitHub'daki `data` dalına gönderir."""
import json
import logging
import math
import shutil
import subprocess
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

from .db import DB, now, parse_ts
from .sources import source_name

log = logging.getLogger(__name__)


def _score(importance: int, nd: int, updated: str) -> float:
    age_h = (datetime.now(timezone.utc) - parse_ts(updated)).total_seconds() / 3600
    return round((importance + 1.5 * math.log2(1 + nd)) * 0.5 ** (max(age_h, 0) / 10), 4)


def story_dict(db: DB, s) -> dict:
    arts = db.q("SELECT source, domain, url, title, published FROM articles WHERE story_id=? ORDER BY published", s["id"])
    by_domain = {}
    for a in arts:  # her yayın organından en güncel haberi göster
        by_domain[a["domain"]] = a
    sources = sorted(by_domain.values(), key=lambda a: a["published"])
    full = s["status"] == "full"
    return {
        "id": s["id"],
        "section": s["section"],
        "kind": "full" if full and s["mode"] == "full" else "brief",
        "importance": s["importance"] or 2,
        "title": s["title"],
        "summary": s["summary"],
        "points": json.loads(s["points"] or "[]") if full and s["mode"] == "full" else [],
        "facts": json.loads(s["facts"] or "[]") if full and s["mode"] == "full" else [],
        "why": (s["why"] or "") if full else "",
        "tags": json.loads(s["tags"] or "[]"),
        "timeline": json.loads(s["timeline"] or "[]") if len(sources) > 1 else [],
        "sources": [{"name": a["source"], "url": a["url"], "title": a["title"], "published": a["published"]}
                    for a in sources],
        "sourceCount": len(sources),
        "firstSeen": s["created_at"],
        "updatedAt": max(s["updated_at"], s["written_at"] or ""),
        "score": _score(s["importance"] or 2, len(sources), s["updated_at"]),
    }


def collect(db: DB, cfg) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(hours=cfg["pipeline"]["publish_window_hours"])).isoformat()
    rows = db.q("SELECT * FROM stories WHERE status IN ('short','full') AND updated_at > ? AND title IS NOT NULL", since)
    stories = [story_dict(db, s) for s in rows]
    stories.sort(key=lambda s: -s["score"])
    return stories


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    if isinstance(data, str):
        tmp.write_text(data, encoding="utf-8")
    else:
        tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)


def _rss(cfg, stories: list[dict], title: str, self_path: str) -> str:
    pc = cfg["publish"]
    site = pc["site_url"].rstrip("/")
    items = []
    for s in sorted(stories, key=lambda s: s["updatedAt"], reverse=True)[:80]:
        body = [f"<p>{escape(s['summary'])}</p>"]
        if s["points"]:
            body.append("<ul>" + "".join(f"<li>{escape(p)}</li>" for p in s["points"]) + "</ul>")
        if s["facts"]:
            body.append("<p>" + " · ".join(f"<b>{escape(f['label'])}:</b> {escape(f['value'])}" for f in s["facts"]) + "</p>")
        if s["why"]:
            body.append(f"<p><i>Neden önemli:</i> {escape(s['why'])}</p>")
        body.append("<p>Kaynaklar: " + ", ".join(f'<a href="{escape(x["url"])}">{escape(x["name"])}</a>'
                                                  for x in s["sources"]) + "</p>")
        items.append(f"""    <item>
      <title>{escape(s['title'])}</title>
      <link>{site}/haber/{s['id']}</link>
      <guid isPermaLink="false">{s['id']}</guid>
      <category>{escape(cfg['sections'][s['section']])}</category>
      <pubDate>{format_datetime(parse_ts(s['firstSeen']))}</pubDate>
      <description><![CDATA[{''.join(body)}]]></description>
    </item>""")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{escape(title)}</title>
    <link>{site}</link>
    <atom:link href="{site}/{self_path}" rel="self" type="application/rss+xml"/>
    <description>{escape(pc['feed_description'])}</description>
    <language>tr</language>
    <lastBuildDate>{format_datetime(datetime.now(timezone.utc))}</lastBuildDate>
    <ttl>15</ttl>
{chr(10).join(items)}
  </channel>
</rss>
"""


def sources_report(db: DB) -> list[dict]:
    out = []
    for f in db.q("SELECT * FROM feeds WHERE active=1 ORDER BY category, url"):
        out.append({"url": f["url"], "name": source_name(f["url"], f["title"]), "category": f["category"],
                    "section": f["section"], "ok": f["fail_count"] == 0 and f["last_ok"] is not None,
                    "lastOk": f["last_ok"], "error": f["last_error"], "items": f["item_count"]})
    return out


def export(db: DB, cfg, stories: list[dict], brief: dict | None, markets: dict | None, stats: dict) -> Path:
    out = cfg.out_dir
    sections = cfg["sections"]
    _write(out / "feed.json", {"generatedAt": now(), "sections": sections, "stories": stories})
    _write(out / "brief.json", brief or {})
    _write(out / "markets.json", markets or {})
    _write(out / "sources.json", {"generatedAt": now(), "feeds": sources_report(db)})
    _write(out / "stats.json", stats)
    title = cfg["publish"]["feed_title"]
    _write(out / "rss.xml", _rss(cfg, stories, title, "rss.xml"))
    for key, name in sections.items():
        _write(out / "rss" / f"{key}.xml", _rss(cfg, [s for s in stories if s["section"] == key],
                                                 f"{title} · {name}", f"rss/{key}.xml"))

    # Günlük arşiv: yayından düşen haberlerin sayfaları da açılabilsin diye
    days = defaultdict(list)
    since = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y%m%d")
    for s in db.q("SELECT * FROM stories WHERE status IN ('short','full') AND title IS NOT NULL AND id >= ?", since):
        days[s["id"][:8]].append(story_dict(db, s))
    for day, items in days.items():
        items.sort(key=lambda s: (-s["importance"], -s["sourceCount"]))
        _write(out / "archive" / f"{day}.json", {"date": day, "stories": items})
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y%m%d")
    for f in (out / "archive").glob("*.json"):
        if f.stem < cutoff:
            f.unlink()
    _write(out / "archive" / "index.json", sorted((f.stem for f in (out / "archive").glob("2*.json")), reverse=True))
    return out


def _git(cwd: Path, *args, check=True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, check=check, capture_output=True, text=True)


def push(cfg, out: Path) -> None:
    """`out/` klasörünü tek commit'lik bir `data` dalı olarak zorla gönderir (geçmiş birikmez)."""
    pc = cfg["publish"]
    if not pc["enabled"] or not shutil.which("git"):
        return
    repo = (Path(cfg.state_dir).parent / pc["repo_dir"]).resolve()
    remote = _git(repo, "remote", "get-url", "origin", check=False).stdout.strip()
    if not remote:
        log.warning("GitHub remote tanımlı değil; yayın atlandı")
        return
    work = cfg.state_dir / "data-repo"
    if not (work / ".git").exists():
        work.mkdir(exist_ok=True)
        _git(work, "init", "-q", "-b", pc["branch"])
        _git(work, "remote", "add", "origin", remote)
    for item in work.iterdir():
        if item.name != ".git":
            shutil.rmtree(item) if item.is_dir() else item.unlink()
    shutil.copytree(out, work, dirs_exist_ok=True)
    (work / "README.md").write_text("Bu dal haber motoru tarafından otomatik üretilir; elle düzenlemeyin.\n", encoding="utf-8")
    _git(work, "checkout", "-q", "--orphan", "_tmp")
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", f"Veri güncellemesi {now()}")
    _git(work, "branch", "-D", pc["branch"], check=False)
    _git(work, "branch", "-m", pc["branch"])
    r = _git(work, "push", "-q", "-f", "origin", pc["branch"], check=False)
    if r.returncode:
        log.error("GitHub'a gönderilemedi: %s", r.stderr.strip())
    else:
        log.info("Veri GitHub'a gönderildi (%s dalı)", pc["branch"])
    _git(work, "gc", "-q", "--prune=now", check=False)
