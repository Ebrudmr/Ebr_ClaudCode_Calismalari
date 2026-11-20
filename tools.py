"""Ajanın kullanabildiği araçlar.

Yalnızca Python standart kütüphanesini kullanır. Her araç sade bir fonksiyondur;
ajan bunları `agent.py` içindeki araç kayıt defteri (TOOLS) üzerinden çağırır.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

SUPPORTED_EXTENSIONS = {".txt", ".md"}

# Bu kelimelerden birini içeren satır acil sayılır (Türkçe küçük harfe çevrildikten sonra).
URGENT_KEYWORDS = ("acil", "asap", "kritik", "hemen", "bugün")
# Son tarihe bu kadar gün (veya daha az) kalmışsa iş acil sayılır.
URGENT_WINDOW_DAYS = 3

# Bir satırı "aksiyon maddesi" yapan işaretler. Satırın başında aranır.
_ACTION_MARKER = re.compile(r"^\s*(?:[-*]\s*)?(\[ \]|aksiyon:|todo:|yapılacak:|acil:)\s*")
_OWNER = re.compile(r"@(\w+)")
_DATE_PATTERNS = (
    # 20.11.2026
    (re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b"), lambda m: (int(m[3]), int(m[2]), int(m[1]))),
    # 2026-12-05
    (re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"), lambda m: (int(m[1]), int(m[2]), int(m[3]))),
)
_DEADLINE_WORDS = re.compile(r"\s*-?\s*son tarih\s*:?\s*", re.IGNORECASE)


def tr_lower(text: str) -> str:
    """Türkçe'ye uygun küçük harf dönüşümü (İ -> i, I -> ı).

    str.lower() "İ" harfini iki karaktere böler; bu da konum hesaplarını bozar.
    """
    return text.replace("İ", "i").replace("I", "ı").lower()


def find_dates(text: str) -> list[tuple[date, tuple[int, int]]]:
    """Metindeki tarihleri (tarih, (başlangıç, bitiş)) olarak, geçtikleri sırayla döndürür."""
    found = []
    for pattern, to_ymd in _DATE_PATTERNS:
        for match in pattern.finditer(text):
            try:
                found.append((date(*to_ymd(match)), match.span()))
            except ValueError:  # 31.02.2026 gibi geçersiz tarihler
                continue
    return sorted(found, key=lambda item: item[1][0])


def read_files(folder: str | Path) -> dict[str, str]:
    """ARAÇ 1: Klasördeki .txt/.md dosyalarını okur.

    Dönüş: {dosya_adı: içerik}. Klasör yoksa veya boşsa boş sözlük döner;
    bu durumda ne yapılacağına ajan karar verir.
    """
    folder = Path(folder)
    if not folder.is_dir():
        return {}
    return {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted(folder.iterdir())
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    }


def extract_actions(text: str, source: str = "", today: date | None = None) -> dict:
    """ARAÇ 2: Metinden aksiyon maddelerini ve acil işleri ayıklar.

    Dönüş sözlüğü:
      aksiyonlar  -> tüm aksiyon maddeleri (her biri bir sözlük)
      acil_isler  -> aksiyonların acil olanları, en acilden başlayarak
      uyarilar    -> aksiyon olmayan ama acil kelime içeren notlar (riskler)
    """
    today = today or date.today()
    actions, warnings = [], []
    meeting_date = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lowered = tr_lower(line)

        # "### 12.11.2026 - ..." gibi başlıklar sonraki maddelerin toplantı tarihini belirler.
        if line.startswith("#"):
            dates = find_dates(line)
            meeting_date = dates[0][0] if dates else meeting_date
            continue

        keywords = [kw for kw in URGENT_KEYWORDS if kw in lowered]
        marker = _ACTION_MARKER.match(lowered)
        if not marker:
            if keywords:
                warnings.append({"not": line.lstrip("-* ").strip(), "kaynak": source,
                                 "toplanti": meeting_date})
            continue

        dates = find_dates(line)
        deadline = dates[-1][0] if dates else None
        owners = _OWNER.findall(line)

        reasons = [f"'{kw}' ifadesi" for kw in keywords]
        if deadline:
            days_left = (deadline - today).days
            if days_left < 0:
                reasons.append(f"{-days_left} gün gecikmiş")
            elif days_left == 0:
                reasons.append("son gün bugün")
            elif days_left <= URGENT_WINDOW_DAYS:
                reasons.append(f"{days_left} gün kaldı")

        actions.append({
            "gorev": _clean_task(line, marker.end(), dates),
            "sorumlu": owners[0] if owners else None,
            "son_tarih": deadline,
            "toplanti": meeting_date,
            "kaynak": source,
            "acil": bool(reasons),
            "acil_nedenleri": reasons,
        })

    urgent = sorted((a for a in actions if a["acil"]),
                    key=lambda a: a["son_tarih"] or today)
    return {"aksiyonlar": actions, "acil_isler": urgent, "uyarilar": warnings}


def _clean_task(line: str, marker_end: int, dates: list) -> str:
    """Satırdan işaret, @sorumlu, tarih ve 'son tarih' kalıplarını atıp görev metnini bırakır."""
    # Tarihleri sondan başa doğru silerek konumların kaymasını önle.
    for _, (start, end) in reversed(dates):
        line = line[:start] + line[end:]
    task = line[marker_end:]
    task = _OWNER.sub("", task)
    task = _DEADLINE_WORDS.sub(" ", task)
    return re.sub(r"\s+", " ", task).strip(" -")
