# Akış

Onlarca Türkçe ve yabancı haber kaynağını 15 dakikada bir tarayan, aynı olayı anlatan haberleri bir araya getirip
**tamamen yerel çalışan bir yapay zekâ modeliyle** tek bir haber kartında derleyen ve bunu hem bir web sitesi hem de RSS
olarak yayınlayan haber akışı.

```
 rss.json (kaynak listesi, saatte bir yeniden okunur)
      │
      ▼
 ┌────────────── engine/ (bu bilgisayarda, systemd servisi) ─────────────────────────────┐
 │ 1. Beslemeleri çek (ETag, hata veren beslemeye artan bekleme)                           │
 │ 2. bge-m3 ile her haberi vektöre çevir (çok dilli: Türkçe ↔ İngilizce eşleşir)          │
 │ 3. Aynı olayı anlatanları grupla (benzerlik + hikâye merkezi; belirsizse modele sor)    │
 │ 4. Tek kaynaklı haberleri toplu ön elemeden geçir (bölüm, önem, kısa başlık)            │
 │ 5. Çok kaynaklı / önemli hikâyeler için haber metinlerini indir, modele derlet:         │
 │    başlık · özet · maddeler · rakamlar · neden önemli · gelişmeler · kaynaklar          │
 │ 6. Saatte bir "Şu an" özeti, piyasa şeridi                                              │
 │ 7. JSON + RSS üret → GitHub'da `data` dalına tek commit olarak gönder                   │
 └─────────────────────────────────────────────────────────────────────────────────────────┘
      │  raw.githubusercontent.com/<kullanıcı>/<repo>/data/…
      ▼
 web/ (Next.js, Vercel) — veriyi dakikada bir tazeler; veri değişince yeniden deploy gerekmez
```

## Neden bu tasarım

- **Model**: 6 GB'lık GTX 1060 için adaylar gerçek haber gruplarıyla ölçüldü (`qwen3.5:4b`, `gemma4:e4b-it-qat`, …).
  Seçim `engine/config.yaml` içindeki `models.llm` satırından değiştirilebilir.
- **Kaynağa saygı**: Kamuya mal olmuş bilgiler (resmî açıklama, skor, kaza, karar) kaynak gösterilerek ayrıntılı derlenir.
  Model bir haberin yayın organına özgü olduğunu (röportaj, özel haber, köşe yazısı, analiz) işaretlerse kartta yalnızca
  kısa özet ve kaynağa bağlantı gösterilir.
- **Uydurmaya karşı**: Model internete çıkmaz; yalnızca indirilen kaynak metinleri görür. Çıktı her zaman JSON şemasıyla
  sınırlanır. Talimatlar çelişkili bilgileri kaynak adıyla belirtmesini ister.
- **Bölüm doğruluğu**: Çok kaynaklı hikâyelerde konuya özel beslemelerin (Spor, Ekonomi…) çoğunluk kararı esas alınır.
- **Depo şişmez**: Veri `data` dalına her seferinde tek commit olarak zorla gönderilir; kod geçmişi `main`'de temiz kalır.

## Kurulum

### 1. Gerekenler

```bash
sudo apt install -y git gh
gh auth login                     # GitHub hesabına giriş
ollama pull gemma4:e4b-it-qat     # yazım modeli
ollama pull bge-m3                # gömme (embedding) modeli
```

`uv` Python paket yöneticisi `~/.local/bin/uv` altında kurulu olmalı.

### 2. Motoru denemek

```bash
cd engine
uv run newsfeed sources          # kaynak listesini oku, beslemeleri göster
uv run newsfeed run --no-push    # tek tur; çıktı engine/out/ altında
uv run newsfeed status
```

İlk turda son 30 saatin ~1500 haberi işlenir; birikim birkaç turda erir.

### 3. Sürekli çalıştırmak

```bash
engine/deploy/install.sh          # systemd kullanıcı servisi olarak kurar
journalctl --user -u akis-engine -f
```

### 4. Siteyi Vercel'e almak

1. Vercel'de **New Project → bu repo**.
2. **Root Directory**: `web`.
3. **Environment Variables**: `DATA_BASE_URL = https://raw.githubusercontent.com/<kullanıcı>/<repo>/data`
4. Deploy. Ardından `engine/config.yaml` içindeki `publish.site_url` değerini Vercel adresinizle güncelleyin
   (RSS'teki bağlantılar için; site kendi RSS'ini zaten doğru adresle sunar).

`web/vercel.json`, `data` dalına yapılan gönderimlerin ve `web/` dışındaki değişikliklerin deploy tetiklemesini engeller.

### Yerel geliştirme

```bash
cd web
echo "DATA_DIR=../engine/out" > .env.local
npm install && npm run dev
```

## Ayarlar (`engine/config.yaml`)

| Ayar | Anlamı |
|---|---|
| `sources.url` | Kaynak listesi. Saatte bir yeniden okunur, yeni beslemeler kendiliğinden eklenir. |
| `sources.category_map` / `ignore` | rss.json kategorilerinin sitedeki bölümlere eşlemesi. Tanınmayan yeni kategoriler adına göre tahmin edilir. |
| `models.llm` | Yazım modeli (Ollama etiketi). |
| `pipeline.interval_minutes` | Tur aralığı. |
| `pipeline.llm_budget_seconds` | Bir turda modele ayrılan süre; bitmeyen işler sonraki tura kalır. |
| `pipeline.join_threshold` / `ask_threshold` / `centroid_threshold` | Gruplama eşikleri (bge-m3 kosinüs benzerliği). |
| `pipeline.full_story_min_importance` | Tek kaynaklı bir haberin ayrıntılı kart olması için gereken önem (1-5). |

## Yayınlanan dosyalar (`data` dalı)

| Dosya | İçerik |
|---|---|
| `feed.json` | Son 36 saatin hikâyeleri (önem × kaynak sayısı × tazelik sırasıyla) |
| `brief.json` | "Şu an" özeti |
| `rss.xml`, `rss/<bölüm>.xml` | RSS 2.0 beslemeleri |
| `archive/YYYYMMDD.json` | Günlük arşiv (30 gün) |
| `sources.json` | Beslemelerin sağlık durumu |
| `markets.json`, `stats.json` | Piyasa şeridi, son turun istatistikleri |
