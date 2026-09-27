"""Komut satırı: `newsfeed run` (tek tur), `newsfeed loop` (sürekli), `newsfeed status`."""
import argparse
import asyncio
import logging
import sys
import time
from datetime import datetime, timezone

from . import markets, pipeline, publish, sources
from .config import load
from .db import DB, now
from .fetch import fetch_feeds
from .llm import LLM

log = logging.getLogger("newsfeed")


def cycle(cfg, db: DB, push: bool = True) -> dict:
    t0 = time.time()
    p = cfg["pipeline"]
    llm = LLM(cfg)
    sources.refresh(db, cfg)
    new = asyncio.run(fetch_feeds(db, cfg))
    embedded = pipeline.embed_new(db, llm)
    joined, created = pipeline.Clusterer(db, llm, cfg).run()
    log.info("Gruplama: %d haber mevcut hikâyelere eklendi, %d yeni hikâye", joined, created)

    dl = pipeline.Deadline(p["llm_budget_seconds"])
    # Önce çok kaynaklı / önemli hikâyeler yazılır, sonra yeni gelenler elenir; kalan süre tekrar yazıma gider.
    written = pipeline.write_stories(db, llm, cfg, pipeline.Deadline(dl.left() * 0.5))
    triaged = pipeline.triage(db, llm, cfg, pipeline.Deadline(dl.left() * 0.7))
    written += pipeline.write_stories(db, llm, cfg, dl)

    stories = publish.collect(db, cfg)
    brief = pipeline.make_brief(db, llm, cfg, [s for s in stories if s["kind"] == "full"] or stories)
    stats = {
        "generatedAt": now(), "model": cfg["models"]["llm"], "embedModel": cfg["models"]["embed"],
        "cycleSeconds": round(time.time() - t0), "newArticles": new, "embedded": embedded,
        "newStories": created, "joined": joined, "triaged": triaged, "written": written,
        "llm": {k: round(v, 1) for k, v in llm.stats.items()},
        "backlog": pipeline.backlog(db, cfg),
        "feeds": db.one("SELECT COUNT(*) c FROM feeds WHERE active=1")["c"],
        "intervalMinutes": p["interval_minutes"],
    }
    out = publish.export(db, cfg, stories, brief, markets.fetch(), stats)
    if push:
        publish.push(cfg, out)
    log.info("Tur bitti: %ds, %d haber yayında, %d yazıldı, %d elendi, LLM %ds",
             stats["cycleSeconds"], len(stories), written, triaged, llm.stats["seconds"])
    return stats


def main(argv=None):
    ap = argparse.ArgumentParser(prog="newsfeed")
    ap.add_argument("command", choices=["run", "loop", "status", "sources"])
    ap.add_argument("--no-push", action="store_true", help="GitHub'a gönderme")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S", stream=sys.stdout)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    cfg = load()
    db = DB(cfg.state_dir / "newsfeed.db")

    if a.command == "sources":
        sources.refresh(db, cfg, force=True)
        for f in db.q("SELECT section, category, url, fail_count, last_error FROM feeds WHERE active=1 ORDER BY section"):
            print(f"{f['section']:10} {f['category']:16} {'HATA ' if f['fail_count'] else 'ok   '} {f['url']}")
    elif a.command == "status":
        for row in db.q("SELECT status, COUNT(*) c FROM stories GROUP BY status"):
            print(f"{row['status']:8} {row['c']}")
        print("makale:", db.one("SELECT COUNT(*) c FROM articles")["c"])
    elif a.command == "run":
        cycle(cfg, db, push=not a.no_push)
    else:
        while True:
            started = time.time()
            try:
                cfg = load()  # ayarlar her turda yeniden okunur
                cycle(cfg, db, push=not a.no_push)
            except Exception:
                log.exception("Tur hata ile bitti; bir sonraki turda yeniden denenecek")
            wait = cfg["pipeline"]["interval_minutes"] * 60 - (time.time() - started)
            if pipeline.backlog(db, cfg) > 10:
                wait = min(wait, 60)  # birikim varken beklemeden devam et
            if wait > 0:
                log.info("Sonraki tur %s UTC", datetime.fromtimestamp(time.time() + wait, timezone.utc).strftime("%H:%M"))
                time.sleep(wait)


if __name__ == "__main__":
    main()
