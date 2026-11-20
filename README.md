# Ebr_ClaudCode_Calismalari

Toplantı notlarını okuyup aksiyon maddelerini ve acil işleri raporlayan basit bir Python ajanı.
Yalnızca Python standart kütüphanesini kullanır (Python 3.10+), ek kurulum gerekmez.

## Çalıştırma

```bash
python3 agent.py                       # notes/ klasörünü okur, rapor.md yazar
python3 agent.py --bugun 2026-11-19    # aciliyeti belirli bir tarihe göre hesapla
python3 agent.py --notlar baska_klasor --rapor cikti.md
```

## Yapı

- `notes/` — analiz edilecek `.txt` / `.md` notları
- `tools.py` — ajanın araçları: `read_files` (klasörü okur), `extract_actions` (aksiyon ve acil işleri ayıklar)
- `agent.py` — Plan -> Araç Kullan -> Raporla döngüsü; sonucu ekrana ve `rapor.md`'ye yazar

## GitHub'da rapor oluşturma

GitHub'da **Actions → Rapor oluştur → Run workflow** ile ajan çalıştırılır ve `rapor.md` değiştiyse repoya kaydedilir
(`.github/workflows/gunluk-rapor.yml`). Otomatik zamanlama yoktur; iş akışı yalnızca elle başlatıldığında çalışır.
