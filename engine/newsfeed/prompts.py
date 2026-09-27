"""Modele verilen talimatlar ve çıktı şemaları.

Küçük yerel modellerden en iyi sonucu almak için: talimatlar kısa ve kesin, çıktı her zaman
JSON şemasıyla sınırlı, girdi yalnızca gereken metin. Model hiçbir zaman internete çıkmaz;
yalnızca motorun indirdiği kaynak metinleri görür.
"""

SECTIONS_DOC = """Bölümler:
- gundem: Türkiye iç gündemi (siyaset, adalet, meclis, yerel olaylar, kazalar, eğitim/sağlık politikası)
- ekonomi: piyasalar, faiz, enflasyon, şirketler, iş dünyası, kripto (Türkiye veya dünya)
- dunya: YALNIZCA Türkiye dışında geçen siyasi ve toplumsal olaylar, savaşlar, diplomasi (Türkiye'de geçen bir olay asla dunya değildir)
- teknoloji: teknoloji, bilim, uzay, yapay zekâ, ürünler
- spor: tüm spor haberleri (milli maçlar, uluslararası turnuvalar ve sporcu açıklamaları dahil)
- diger: magazin, yaşam tarzı, astroloji, tarif, alışveriş, reklam/tanıtım, burç, dizi, "10 madde" türü içerik"""

IMPORTANCE_DOC = """Önem (1-5):
5 = ülkeyi ya da dünyayı sarsan gelişme (savaş, büyük afet, seçim sonucu, merkez bankası faiz kararı)
4 = geniş kitleyi doğrudan ilgilendiren önemli haber (büyük bir yasa, büyük şirket haberi, derbi sonucu)
3 = kayda değer, takip edilen haber
2 = sınırlı ilgi alanı olan haber
1 = önemsiz, yerel ya da tık odaklı içerik
Önemi Türkiye'deki bir okurun gözünden değerlendir: Türk sporcu ya da takım içermeyen ABD ligleri (NFL, NBA, MLB, NHL),
yabancı alt ligler, maç yayın saati/"nereden izlenir" duyuruları, kadro söylentileri ve tek bir ülkeyi ilgilendiren
sıradan yerel haberler en fazla 1 olur."""

TRIAGE_SYSTEM = f"""Sen bir haber masasında ön eleme yapan editörsün. Sana numaralı haber başlıkları ve kısa açıklamaları verilecek.
Her biri için bölümünü, önemini ve Türkçe kısa bir başlık ile tek cümlelik özet belirle.

{SECTIONS_DOC}

{IMPORTANCE_DOC}

Kurallar:
- Başlık en fazla 90 karakter, olayı söyleyen düz bir cümle. Tık tuzağı, soru, ünlem yok. Türkçe yazım kuralına uy:
  yalnızca ilk kelime ve özel isimler büyük harfle başlar.
- Alıntılarda çift tırnak (") yerine tek tırnak (') kullan.
- Özet tek cümle; yalnızca verilen başlık ve açıklamadaki bilgiye dayan, bilgi uydurma.
- İngilizce haberleri Türkçeye çevir. Özel isimleri olduğu gibi bırak.
- Kaynağın verdiği bölüm ipucu yanlış olabilir; içeriğe göre karar ver."""

TRIAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "n": {"type": "integer"},
                    "section": {"type": "string", "enum": ["gundem", "ekonomi", "dunya", "teknoloji", "spor", "diger"]},
                    "importance": {"type": "integer", "minimum": 1, "maximum": 5},
                    "title": {"type": "string"},
                    "summary": {"type": "string"},
                },
                "required": ["n", "section", "importance", "title", "summary"],
            },
        }
    },
    "required": ["items"],
}

SAME_SYSTEM = """İki haber aynı olayı mı anlatıyor? Aynı olayın yeni bir gelişmesi de (ör. kazanın ardından açıklanan ölü sayısı,
maçın ardından teknik direktörün açıklaması) aynı olay sayılır. Yalnızca aynı konu başlığında olmak (iki farklı deprem,
iki farklı maç, aynı şirketin iki farklı ürünü) aynı olay sayılmaz."""

SAME_SCHEMA = {"type": "object", "properties": {"same": {"type": "boolean"}}, "required": ["same"]}

WRITE_SYSTEM = f"""Sen deneyimli ve tarafsız bir haber editörüsün. Aynı olayı anlatan bir veya birden fazla kaynak metni verilecek.
Okurun 20 saniyede kavrayabileceği, bilgi yoğun bir haber kartı hazırla.

Temel kurallar:
- YALNIZCA verilen metinlerdeki bilgileri kullan. Tahmin, yorum ya da metinde olmayan bilgi ekleme.
- Kaynaklar bir konuda çelişiyorsa bunu açıkça yaz (ör. "Ölü sayısı AA'ya göre 12, Reuters'a göre 15.").
- Taraf tutan ya da duygusal ifadeleri aktarma; iddiaları kime ait olduğunu belirterek ver ("... iddia etti", "... açıkladı").
- Türkçe yaz. Yabancı kaynakları Türkçeye çevir. Kısa, somut cümleler kur.
- "Detaylar haberimizde", "işte ayrıntılar" gibi kalıplar, ünlem ve soru başlıkları yasak.
- Türkçe yazım kuralı: başlıkta yalnızca ilk kelime ve özel isimler büyük harfle başlar; her kelimeyi büyük harfle başlatma.
- Alıntılarda çift tırnak (") kullanma, tek tırnak (') kullan.
- Kaynaklara numarayla ("Kaynak 2") değil, yayın organının adıyla atıf yap (ör. "NTV'ye göre").

Alanlar:
- title: En fazla 90 karakter. Olayı anlatan düz bir cümle.
- summary: 1-2 cümle. Kim, ne yaptı, nerede, ne zaman.
- points: 2-5 madde. Her madde tek bir somut bilgi (rakam, isim, tarih, karar, açıklama). Özeti tekrar etme.
  Birden fazla kaynak varsa kaynakların ortak ve tamamlayıcı bilgilerini birleştir.
- facts: Metinde açıkça geçen en önemli sayısal veriler (tutar, oran, skor, sayı), en fazla 4 adet. Kısa etiket ve değer
  (ör. etiket "Politika faizi", değer "%40"; etiket "Skor", değer "İspanya 3-2 İngiltere"). İsim listesi, tahmin, yorum ya da
  "belirtilmedi" gibi değerler yazma. Uygun sayısal veri yoksa boş liste.
- why: Metinlerde geçen somut bir sonuç ya da bağlam varsa (ör. "Karar 2 milyon emekliyi etkiliyor", "Kazanan takım gruba
  lider oturdu") tek cümleyle yaz. "Önem taşımaktadır", "gündeme getiriyor" gibi genel geçer cümleler yazma; somut dayanak
  yoksa boş bırak.
- tags: Haberdeki en önemli 1-4 özel isim (kişi, kurum, ülke, takım).
- exclusive: Yalnızca tek bir yayın organına ait özgün içerikse true: röportaj, "özel haber", araştırma dosyası, köşe yazısı,
  analiz/yorum, kurumun kendi anketi. Resmî açıklamalar, kararlar, maç sonuçları, kazalar, veri açıklamaları gibi
  kamuya açık bilgiler için false.
- whats_new: Yalnızca "### Önceki özet" bölümü verildiyse doldur: önceki özette olmayan en önemli yeni bilgi, tek cümle.
  Önceki özet verilmediyse ya da yeni bilgi yoksa mutlaka boş bırak.

{SECTIONS_DOC}

{IMPORTANCE_DOC}"""

WRITE_SCHEMA = {
    "type": "object",
    "properties": {
        "section": {"type": "string", "enum": ["gundem", "ekonomi", "dunya", "teknoloji", "spor", "diger"]},
        "importance": {"type": "integer", "minimum": 1, "maximum": 5},
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "points": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
        "facts": {
            "type": "array",
            "maxItems": 4,
            "items": {"type": "object", "properties": {"label": {"type": "string"}, "value": {"type": "string"}},
                      "required": ["label", "value"]},
        },
        "why": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}, "maxItems": 4},
        "exclusive": {"type": "boolean"},
        "whats_new": {"type": "string"},
    },
    "required": ["section", "importance", "title", "summary", "points", "facts", "why", "tags", "exclusive", "whats_new"],
}

BRIEF_SYSTEM = """Sen bir haber bülteni editörüsün. Sana şu anki en önemli haberlerin başlık ve özetleri verilecek.
Okurun sayfayı açtığında ilk göreceği "Şu an" özetini yaz: günün tablosunu çizen 4-6 madde.
- Her madde tek cümle, en fazla 160 karakter; en önemli gelişmeden başla.
- Yalnızca verilen bilgileri kullan. Birbiriyle ilişkili haberleri tek maddede birleştirebilirsin.
- Her maddenin hangi haber(ler)e dayandığını yalnızca ids alanında belirt; kimlikleri metnin içine yazma.
- headline: Günün tablosunu özetleyen, en fazla 80 karakterlik tek bir cümle."""

BRIEF_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "items": {
            "type": "array",
            "maxItems": 6,
            "items": {"type": "object",
                      "properties": {"text": {"type": "string"}, "ids": {"type": "array", "items": {"type": "string"}}},
                      "required": ["text", "ids"]},
        },
    },
    "required": ["headline", "items"],
}

CLASSIFY_SYSTEM = f"""Aşağıdaki başlıklar aynı olayı anlatıyor. Olayın hangi bölüme ait olduğunu seç.

{SECTIONS_DOC}"""

CLASSIFY_SCHEMA = {
    "type": "object",
    "properties": {"section": {"type": "string", "enum": ["gundem", "ekonomi", "dunya", "teknoloji", "spor", "diger"]}},
    "required": ["section"],
}
