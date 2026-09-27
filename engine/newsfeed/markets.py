"""Sayfanın üstündeki piyasa şeridi için anlık fiyatlar (Yahoo Finance, anahtarsız)."""
import logging

import httpx

from .db import now

log = logging.getLogger(__name__)

SYMBOLS = [
    ("USDTRY=X", "Dolar", 4),
    ("EURTRY=X", "Euro", 4),
    ("GRAM", "Gram altın", 0),
    ("XU100.IS", "BIST 100", 0),
    ("BZ=F", "Brent", 2),
    ("BTC-USD", "Bitcoin", 0),
]


def _quote(client: httpx.Client, symbol: str) -> tuple[float, float] | None:
    try:
        r = client.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}", params={"range": "1d", "interval": "15m"})
        m = r.json()["chart"]["result"][0]["meta"]
        return float(m["regularMarketPrice"]), float(m.get("chartPreviousClose") or m["previousClose"])
    except Exception as e:  # noqa: BLE001
        log.debug("Piyasa verisi alınamadı %s: %s", symbol, e)
        return None


def fetch() -> dict | None:
    with httpx.Client(headers={"User-Agent": "Mozilla/5.0"}, timeout=10) as c:
        q = {s: _quote(c, s) for s, _, _ in SYMBOLS if s != "GRAM"}
        gold = _quote(c, "GC=F")
    if gold and q.get("USDTRY=X"):
        # ons (USD) -> gram (TL)
        usd, usd_prev = q["USDTRY=X"]
        q["GRAM"] = (gold[0] * usd / 31.1035, gold[1] * usd_prev / 31.1035)
    items = []
    for sym, label, digits in SYMBOLS:
        if q.get(sym):
            price, prev = q[sym]
            items.append({"symbol": sym, "label": label, "price": round(price, digits),
                          "change": round((price - prev) / prev * 100, 2) if prev else 0.0,
                          "unit": {"BZ=F": "$", "BTC-USD": "$", "XU100.IS": ""}.get(sym, "₺")})
    return {"updatedAt": now(), "items": items} if items else None
