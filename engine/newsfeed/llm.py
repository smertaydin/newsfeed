"""Ollama istemcisi: gömme (embedding) ve şemaya bağlı JSON üretimi."""
import json
import logging
import time

import httpx
import numpy as np

log = logging.getLogger(__name__)


class LLM:
    def __init__(self, cfg):
        m = cfg["models"]
        self.host, self.model, self.embed_model = m["host"], m["llm"], m["embed"]
        self.num_ctx, self.keep_alive = m["num_ctx"], m["keep_alive"]
        self.http = httpx.Client(base_url=self.host, timeout=600)
        self.stats = {"calls": 0, "seconds": 0.0, "in_tokens": 0, "out_tokens": 0}

    def embed(self, texts: list[str], batch: int = 32) -> np.ndarray:
        out = []
        for i in range(0, len(texts), batch):
            r = self.http.post("/api/embed", json={"model": self.embed_model, "input": texts[i:i + batch],
                                                   "keep_alive": "30s", "truncate": True})
            r.raise_for_status()
            out.extend(r.json()["embeddings"])
        v = np.asarray(out, dtype=np.float32)
        return v / np.linalg.norm(v, axis=1, keepdims=True).clip(1e-6)

    def unload_embedder(self):
        # 6 GB VRAM'de iki model birlikte zor sığar; gömme işi bitince onu boşaltıyoruz.
        self.http.post("/api/embed", json={"model": self.embed_model, "input": [], "keep_alive": 0})

    def json(self, system: str, user: str, schema: dict, max_tokens: int = 1200, temperature: float = 0.2) -> dict | None:
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "format": schema,
            "stream": False,
            "think": False,
            "keep_alive": self.keep_alive,
            "options": {"num_ctx": self.num_ctx, "temperature": temperature, "num_predict": max_tokens,
                        "repeat_penalty": 1.05},
        }
        for attempt in range(2):
            t = time.time()
            try:
                r = self.http.post("/api/chat", json=body)
                r.raise_for_status()
                data = r.json()
            except httpx.HTTPError as e:
                log.warning("LLM isteği başarısız: %s", e)
                continue
            self.stats["calls"] += 1
            self.stats["seconds"] += time.time() - t
            self.stats["in_tokens"] += data.get("prompt_eval_count", 0)
            self.stats["out_tokens"] += data.get("eval_count", 0)
            try:
                return json.loads(data["message"]["content"])
            except (json.JSONDecodeError, KeyError):
                log.warning("LLM geçersiz JSON döndürdü (deneme %d)", attempt + 1)
                body["options"]["temperature"] = 0.4
        return None
