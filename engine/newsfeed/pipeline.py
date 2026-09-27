"""Gömme, olaylara göre gruplama, ön eleme, yazım ve bülten adımları."""
import asyncio
import hashlib
import json
import logging
import math
import re
import time
from collections import Counter
from datetime import datetime, timedelta, timezone

import numpy as np

from . import prompts
from .db import DB, from_blob, now, parse_ts, to_blob
from .fetch import fetch_bodies
from .llm import LLM

log = logging.getLogger(__name__)


def _hours_ago(h: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=h)).isoformat(timespec="seconds")


def embed_new(db: DB, llm: LLM) -> int:
    rows = db.q("SELECT id, title, description FROM articles WHERE emb IS NULL")
    if not rows:
        return 0
    texts = [f"{r['title']}\n{(r['description'] or '')[:400]}" for r in rows]
    vecs = llm.embed(texts)
    for r, v in zip(rows, vecs):
        db.x("UPDATE articles SET emb=? WHERE id=?", to_blob(v), r["id"])
    db.commit()
    llm.unload_embedder()
    return len(rows)


class Clusterer:
    """Yeni haberleri son 48 saatin hikâyelerine bağlar ya da yeni hikâye açar.

    Bir haberin hikâyeye katılması için hem hikâyedeki en benzer habere hem de hikâyenin
    merkezine (üyelerin ortalamasına) yeterince yakın olması gerekir. Böylece "A~B, B~C"
    zinciriyle aynı takımın/kişinin tüm haberleri tek bir yığına dönüşmez.
    """

    def __init__(self, db: DB, llm: LLM, cfg):
        self.db, self.llm, self.p = db, llm, cfg["pipeline"]
        self.member_story: list[str] = []
        self.member_titles: list[str] = []
        self.vecs = np.zeros((0, 1024), dtype=np.float32)
        self.sums: dict[str, np.ndarray] = {}
        self.judged = 0
        rows = db.q("""SELECT a.story_id, a.emb, a.title FROM articles a JOIN stories s ON s.id=a.story_id
                       WHERE s.updated_at > ? AND a.emb IS NOT NULL""", _hours_ago(self.p["story_window_hours"]))
        if rows:
            self.vecs = np.stack([from_blob(r["emb"]) for r in rows])
            for r, v in zip(rows, self.vecs):
                self.member_story.append(r["story_id"])
                self.member_titles.append(r["title"])
                self.sums[r["story_id"]] = self.sums.get(r["story_id"], 0) + v

    def _add_member(self, sid, vec, title):
        self.member_story.append(sid)
        self.member_titles.append(title)
        self.vecs = np.vstack([self.vecs, vec[None, :]]) if len(self.vecs) else vec[None, :]
        self.sums[sid] = self.sums.get(sid, 0) + vec

    def _centroid_sim(self, sid, vec) -> float:
        c = self.sums[sid]
        return float(c @ vec / max(np.linalg.norm(c), 1e-6))

    def _same_event(self, a_title: str, a_desc: str, b_title: str) -> bool:
        if self.judged >= self.p["max_judge_calls"]:
            return False
        self.judged += 1
        res = self.llm.json(prompts.SAME_SYSTEM, f"Haber A: {a_title}\n{a_desc[:300]}\n\nHaber B: {b_title}",
                            prompts.SAME_SCHEMA, max_tokens=20, temperature=0)
        return bool(res and res.get("same"))

    def _match(self, r, vec) -> str | None:
        if not len(self.vecs):
            return None
        sims = self.vecs @ vec
        p = self.p
        # en benzer iki farklı hikâyeye bak
        tried = set()
        for i in np.argsort(-sims)[:8]:
            sid, best = self.member_story[i], float(sims[i])
            if sid in tried:
                continue
            tried.add(sid)
            if best < p["ask_threshold"] or len(tried) > 2:
                break
            cen = self._centroid_sim(sid, vec)
            if best >= p["join_threshold"] and cen >= p["centroid_threshold"]:
                return sid
            if cen >= p["centroid_threshold"] - 0.06 and self._same_event(
                    r["title"], r["description"] or "", self.member_titles[i]):
                return sid
        return None

    def run(self) -> tuple[int, int]:
        rows = self.db.q("SELECT * FROM articles WHERE story_id IS NULL AND emb IS NOT NULL ORDER BY published")
        joined = created = 0
        for r in rows:
            vec = from_blob(r["emb"])
            sid = self._match(r, vec)
            ts = r["published"]
            if sid:
                joined += 1
                self.db.x("UPDATE stories SET updated_at=MAX(updated_at, ?) WHERE id=?", ts, sid)
            else:
                created += 1
                sid = parse_ts(ts).strftime("%Y%m%d") + "-" + hashlib.sha1(r["id"].encode()).hexdigest()[:8]
                self.db.x("INSERT INTO stories(id, created_at, updated_at) VALUES (?, ?, ?)", sid, ts, ts)
            self.db.x("UPDATE articles SET story_id=? WHERE id=?", sid, r["id"])
            self._add_member(sid, vec, r["title"])
        self.db.commit()
        if self.judged:
            log.info("Belirsiz %d eşleşme modele soruldu", self.judged)
        return joined, created


def story_articles(db: DB, sid: str):
    return db.q("SELECT * FROM articles WHERE story_id=? ORDER BY published", sid)


def n_sources(db: DB, sid: str) -> int:
    return db.one("SELECT COUNT(DISTINCT domain) c FROM articles WHERE story_id=?", sid)["c"]


class Deadline:
    def __init__(self, seconds):
        self.end = time.time() + seconds

    def left(self) -> float:
        return self.end - time.time()


def triage(db: DB, llm: LLM, cfg, dl: Deadline) -> int:
    """Yeni tek kaynaklı hikâyeleri toplu halde sınıflandırır ve kısa kart üretir."""
    # çok kaynaklı hikâyeler ön elemeye girmez, doğrudan yazılır
    pending = db.q("""SELECT s.id FROM stories s JOIN articles a ON a.story_id=s.id WHERE s.status='pending'
                      AND s.updated_at > ? GROUP BY s.id HAVING COUNT(DISTINCT a.domain)=1
                      ORDER BY s.updated_at DESC""", _hours_ago(cfg["pipeline"]["triage_max_age_hours"]))
    size, done = cfg["pipeline"]["triage_batch"], 0
    for i in range(0, len(pending), size):
        if dl.left() < 30:
            break
        batch = pending[i:i + size]
        lines, heads = [], []
        for n, s in enumerate(batch, 1):
            a = story_articles(db, s["id"])[0]
            heads.append(a)
            lines.append(f"[{n}] ({a['source']}, bölüm ipucu: {a['section_hint']})\nBaşlık: {a['title']}\n"
                         f"Açıklama: {(a['description'] or '-')[:350]}")
        res = llm.json(prompts.TRIAGE_SYSTEM, "\n\n".join(lines), prompts.TRIAGE_SCHEMA, max_tokens=180 * len(batch))
        if not res:
            continue
        by_n = {it["n"]: it for it in res.get("items", []) if isinstance(it, dict) and "n" in it}
        for n, s in enumerate(batch, 1):
            it = by_n.get(n)
            if not it or not it.get("title"):
                continue
            status = "hidden" if it["section"] == "diger" or int(it["importance"]) <= 1 else "short"
            db.x("""UPDATE stories SET status=?, section=?, importance=?, title=?, summary=?, mode='brief'
                    WHERE id=? AND status='pending'""",
                 status, it["section"], max(1, min(5, int(it["importance"]))), it["title"].strip(),
                 it["summary"].strip(), s["id"])
            done += 1
        db.commit()
    return done


def _write_candidates(db: DB, cfg):
    p = cfg["pipeline"]
    rows = db.q("""SELECT s.*, COUNT(a.id) n, COUNT(DISTINCT a.domain) nd FROM stories s JOIN articles a ON a.story_id=s.id
                   WHERE s.status IN ('pending','short','full') AND s.updated_at > ?
                   GROUP BY s.id HAVING n > s.written_n""", _hours_ago(p["publish_window_hours"]))
    out = []
    for r in rows:
        if r["nd"] >= 2 or (r["status"] != "pending" and (r["importance"] or 0) >= p["full_story_min_importance"]):
            # önce çok kaynaklı ve önemli olanlar; yeni hikâyeler güncellemelerden önce yazılır
            prio = (r["importance"] or 2) * 2 + math.log2(1 + r["nd"]) * 3 + (2 if r["status"] != "full" else 0)
            out.append((prio, r))
    out.sort(key=lambda t: -t[0])
    return [r for _, r in out]


def voted_section(arts) -> str | None:
    """Konuya özel beslemelerin (Spor, Ekonomi...) çoğunluk kararı. Genel beslemeler 'gundem' olarak
    işaretlendiğinden oylamaya katılmaz; oylama yoksa karar modele kalır."""
    counts = Counter(a["section_hint"] for a in arts if a["section_hint"] != "gundem")
    if not counts:
        return None
    sec, c = counts.most_common(1)[0]
    return sec if c >= 2 and c >= 0.5 * len(arts) else None


def backlog(db: DB, cfg) -> int:
    """Yazılmayı ya da elenmeyi bekleyen iş sayısı."""
    pending = db.one("SELECT COUNT(*) c FROM stories WHERE status='pending' AND updated_at > ?",
                     _hours_ago(cfg["pipeline"]["triage_max_age_hours"]))["c"]
    return pending + len(_write_candidates(db, cfg))


def classify(llm: LLM, arts) -> str | None:
    """Bölümü yalnızca başlıklardan belirleyen kısa çağrı; uzun metin okurken yapılan seçimden daha isabetli."""
    titles = "\n".join(f"- {a['title']}" for a in arts[:8])
    res = llm.json(prompts.CLASSIFY_SYSTEM, titles, prompts.CLASSIFY_SCHEMA, max_tokens=20, temperature=0)
    return res.get("section") if res else None


def _pick_sources(arts, k: int):
    """Farklı yayın organlarından, metni olan en fazla k kaynak seç."""
    seen, picked = set(), []
    for a in sorted(arts, key=lambda a: (a["body_status"] != "ok", a["published"])):
        if a["domain"] in seen:
            continue
        seen.add(a["domain"])
        picked.append(a)
    return picked[:k]


TERMINAL = tuple(".!?…'\"”’)")


def clean_write(res: dict) -> dict | None:
    """Modelin çıktısındaki bariz bozuklukları ayıklar; kurtarılamazsa None döner."""
    title, summary = res.get("title", "").strip(), res.get("summary", "").strip()
    if len(title) < 15 or len(summary) < 40 or not summary.endswith(TERMINAL):
        return None
    res["points"] = [p.strip() for p in res.get("points", []) if len(p.strip().split()) >= 5]
    # sayı içermeyen "rakam"lar ve kaynak numarasına atıflar ayıklanır
    res["facts"] = [f for f in res.get("facts", [])
                    if f.get("label") and re.search(r"\d", f.get("value", "")) and not re.search(r"[Kk]aynak \d", f["label"])][:4]
    why = res.get("why", "").strip()
    if re.search(r"(önem taşı|önemli bir|önem arz|gündeme getir|dikkat çek)", why):
        why = ""
    res["why"] = why
    res["title"], res["summary"] = title.rstrip("."), summary
    return res


def write_stories(db: DB, llm: LLM, cfg, dl: Deadline) -> int:
    p = cfg["pipeline"]
    done = 0
    for s in _write_candidates(db, cfg):
        if dl.left() < 45:
            log.info("Yazım bütçesi doldu; kalanlar sonraki tura")
            break
        arts = story_articles(db, s["id"])
        asyncio.run(fetch_bodies(db, cfg, [a["id"] for a in arts[-12:]]))
        arts = story_articles(db, s["id"])
        chosen = _pick_sources(arts, p["max_sources_per_prompt"])
        budget = p["max_chars_per_source"] if len(chosen) > 2 else p["max_chars_per_source"] * 2
        parts = []
        for i, a in enumerate(chosen, 1):
            text = a["body"] or a["description"] or ""
            local = parse_ts(a["published"]).astimezone(timezone(timedelta(hours=3)))
            parts.append(f"### Kaynak {i}: {a['source']} ({local:%d.%m.%Y %H:%M})\nBaşlık: {a['title']}\n{text[:budget]}")
        hints = Counter(a["section_hint"] for a in arts)
        parts.append("### Beslemelerin bölüm etiketleri (ipucu)\n" + ", ".join(f"{k}×{v}" for k, v in hints.most_common()))
        prev = ""
        if s["status"] == "full" and s["summary"]:
            prev = f"\n\n### Önceki özet\n{s['title']}. {s['summary']} " + " ".join(json.loads(s["points"] or "[]"))
        res = None
        for temp in (0.2, 0.5):
            raw = llm.json(prompts.WRITE_SYSTEM, "\n\n".join(parts) + prev, prompts.WRITE_SCHEMA, max_tokens=900,
                           temperature=temp)
            res = clean_write(raw) if raw else None
            if res:
                break
        if not res:
            log.warning("Hikâye yazılamadı: %s", s["id"])
            continue
        nd = len({a["domain"] for a in arts})
        exclusive = bool(res.get("exclusive")) and nd == 1
        section = voted_section(arts) or classify(llm, arts) or res["section"]
        section = section if section in cfg["sections"] else None
        timeline = json.loads(s["timeline"])
        if prev and res.get("whats_new", "").strip():
            timeline.append({"t": now(), "text": res["whats_new"].strip(), "n": nd})
        elif not timeline:
            timeline.append({"t": arts[0]["published"], "text": "İlk haber: " + arts[0]["source"], "n": 1})
        db.x("""UPDATE stories SET status=?, section=COALESCE(?, section), importance=?, mode=?, title=?, summary=?,
                points=?, facts=?, why=?, tags=?, timeline=?, written_at=?, written_n=? WHERE id=?""",
             "full" if section else "hidden", section, max(1, min(5, int(res["importance"]))),
             "brief" if exclusive else "full", res["title"].strip(), res["summary"].strip(),
             json.dumps([x.strip() for x in res["points"] if x.strip()], ensure_ascii=False),
             json.dumps(res["facts"], ensure_ascii=False), res["why"], json.dumps(res["tags"], ensure_ascii=False),
             json.dumps(timeline[-12:], ensure_ascii=False), now(), len(arts), s["id"])
        db.commit()
        done += 1
    return done


def make_brief(db: DB, llm: LLM, cfg, stories: list[dict]) -> dict | None:
    last = db.meta_get("brief")
    if last and parse_ts(last["generated_at"]) > datetime.now(timezone.utc) - timedelta(
            minutes=cfg["pipeline"]["brief_every_minutes"]):
        return last
    top = stories[:18]
    if len(top) < 5:
        return last
    text = "\n".join(f"[{s['id']}] ({cfg['sections'][s['section']]}, {s['sourceCount']} kaynak) {s['title']}: {s['summary']}"
                     for s in top)
    res = llm.json(prompts.BRIEF_SYSTEM, text, prompts.BRIEF_SCHEMA, max_tokens=700)
    if not res or not res.get("items"):
        return last
    valid = {s["id"] for s in top}
    strip_ids = lambda t: re.sub(r"\s*[\[(]?\d{8}-[0-9a-f]{8}(,\s*\d{8}-[0-9a-f]{8})*[\])]?", "", t).strip()
    brief = {"generated_at": now(), "headline": res["headline"].strip(),
             "items": [{"text": strip_ids(it["text"]), "ids": [i for i in it["ids"] if i in valid]} for it in res["items"]]}
    db.meta_set("brief", brief)
    return brief
