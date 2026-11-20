"""Toplantı notlarını analiz eden basit ajan: Plan -> Araç Kullan -> Raporla.

Çalıştırma:
    python3 agent.py
    python3 agent.py --notlar notes --rapor rapor.md --bugun 2026-11-19
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import tools

BASE_DIR = Path(__file__).resolve().parent

# Ajanın kullanabildiği araçlar. Yeni bir araç eklemek için buraya kaydetmek yeterli.
TOOLS = {
    "dosyalari_oku": tools.read_files,
    "aksiyonlari_ayikla": tools.extract_actions,
}


@dataclass
class Step:
    """Ajanın çalıştıracağı tek bir araç çağrısı."""
    tool: str
    args: dict = field(default_factory=dict)
    reason: str = ""


class NotesAgent:
    def __init__(self, notes_dir: Path, report_path: Path, today: date):
        self.notes_dir = notes_dir
        self.report_path = report_path
        self.today = today
        self.files: dict[str, str] = {}
        self.actions: list[dict] = []
        self.warnings: list[dict] = []
        self.decision = ""
        self.log: list[str] = []

    # --- yardımcılar -----------------------------------------------------
    def _log(self, phase: str, message: str) -> None:
        entry = f"[{phase}] {message}"
        self.log.append(entry)
        print(entry)

    # --- 1) PLAN ---------------------------------------------------------
    def plan(self) -> list[Step]:
        """Başlangıç planı: önce notları oku. Sonraki adımları ajan gözlemlerine göre ekler."""
        steps = [Step("dosyalari_oku", {"folder": self.notes_dir},
                      f"'{self.notes_dir.name}/' klasöründeki notları oku")]
        self._log("PLAN", "Hedef: notlardaki aksiyon maddelerini ve acil işleri raporlamak.")
        for i, step in enumerate(steps, 1):
            self._log("PLAN", f"Adım {i}: {step.tool} -> {step.reason}")
        return steps

    # --- 2) ARAÇ KULLAN (döngü) -------------------------------------------
    def run(self) -> str:
        queue = deque(self.plan())
        while queue:
            step = queue.popleft()
            self._log("ARAÇ", f"{step.tool} çağrılıyor ({step.reason})")
            result = TOOLS[step.tool](**step.args)
            next_steps = self.observe(step, result)
            if next_steps is None:  # ajan durmaya karar verdi
                break
            queue.extend(next_steps)
        self.decide()
        return self.report()

    def observe(self, step: Step, result) -> list[Step] | None:
        """Araç sonucunu değerlendirir; sıradaki adımları döndürür (None = dur)."""
        if step.tool == "dosyalari_oku":
            self.files = result
            if not result:
                self._log("KARAR", f"'{self.notes_dir}' içinde okunacak not yok; işlem durduruluyor.")
                return None
            self._log("GÖZLEM", f"{len(result)} dosya okundu: {', '.join(result)}")
            # Her dosya için ayrı bir ayıklama adımı planla.
            return [Step("aksiyonlari_ayikla",
                         {"text": text, "source": name, "today": self.today},
                         f"{name} içindeki aksiyonları ayıkla")
                    for name, text in result.items()]

        if step.tool == "aksiyonlari_ayikla":
            self.actions.extend(result["aksiyonlar"])
            self.warnings.extend(result["uyarilar"])
            self._log("GÖZLEM", f"{step.args['source']}: {len(result['aksiyonlar'])} aksiyon, "
                                f"{len(result['acil_isler'])} acil, {len(result['uyarilar'])} uyarı")
            return []

        raise ValueError(f"Bilinmeyen araç: {step.tool}")

    def decide(self) -> None:
        """Toplanan verilere bakarak önceliklendirme kararı verir."""
        urgent = [a for a in self.actions if a["acil"]]
        overdue = [a for a in urgent if a["son_tarih"] and a["son_tarih"] < self.today]
        unassigned = [a for a in self.actions if not a["sorumlu"]]

        if not self.actions:
            self.decision = "Notlarda aksiyon maddesi bulunamadı; takip gerektiren iş yok."
        elif urgent:
            parts = [f"Önce {len(urgent)} acil işe odaklanılmalı"]
            if overdue:
                parts.append(f"bunların {len(overdue)} tanesi gecikmiş, hemen ele alınmalı")
            self.decision = ", ".join(parts) + "."
        else:
            self.decision = "Acil iş yok; aksiyonlar son tarih sırasıyla takip edilebilir."
        if unassigned:
            self.decision += f" {len(unassigned)} aksiyonun sorumlusu yok, atanmalı."
        self._log("KARAR", self.decision)

    # --- 3) RAPORLA -------------------------------------------------------
    def report(self) -> str:
        urgent = sorted((a for a in self.actions if a["acil"]),
                        key=lambda a: a["son_tarih"] or self.today)
        others = sorted((a for a in self.actions if not a["acil"]),
                        key=lambda a: a["son_tarih"] or date.max)

        lines = [
            "# Toplantı Notları Raporu",
            "",
            f"_Rapor tarihi: {_fmt(self.today)} · Kaynak: `{self.notes_dir.name}/` "
            f"({len(self.files)} dosya)_",
            "",
            "## Özet",
            "",
            f"- Toplam aksiyon: **{len(self.actions)}**",
            f"- Acil iş: **{len(urgent)}**",
            f"- Ajanın kararı: {self.decision}",
            "",
            "## Acil İşler",
            "",
            *_table(urgent, with_reason=True),
            "",
            "## Diğer Aksiyonlar",
            "",
            *_table(others, with_reason=False),
            "",
            "## Kişi Bazında İş Yükü",
            "",
        ]
        totals = Counter(a["sorumlu"] or "(atanmamış)" for a in self.actions)
        urgent_counts = Counter(a["sorumlu"] or "(atanmamış)" for a in urgent)
        lines += [f"- **{who}**: {n} iş ({urgent_counts[who]} acil)"
                  for who, n in totals.most_common()] or ["_Aksiyon yok._"]

        lines += ["", "## Dikkat Edilecek Notlar", ""]
        lines += [f"- {w['not']} _({_fmt(w['toplanti'])}, {w['kaynak']})_"
                  for w in self.warnings] or ["_Yok._"]

        lines += ["", "## Ajan Adımları", ""]
        lines += [f"{i}. `{entry}`" for i, entry in enumerate(self.log, 1)]

        text = "\n".join(lines) + "\n"
        self.report_path.write_text(text, encoding="utf-8")
        self._log("RAPOR", f"Rapor yazıldı: {self.report_path}")
        return text


def _fmt(d: date | None) -> str:
    return d.strftime("%d.%m.%Y") if d else "-"


def _table(actions: list[dict], with_reason: bool) -> list[str]:
    if not actions:
        return ["_Yok._"]
    header = ["#", "Görev", "Sorumlu", "Son tarih", "Toplantı"]
    if with_reason:
        header.append("Neden acil")
    rows = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for i, a in enumerate(actions, 1):
        cells = [str(i), a["gorev"], a["sorumlu"] or "-", _fmt(a["son_tarih"]), _fmt(a["toplanti"])]
        if with_reason:
            cells.append(", ".join(a["acil_nedenleri"]))
        rows.append("| " + " | ".join(c.replace("|", "\\|") for c in cells) + " |")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Toplantı notlarından aksiyon raporu çıkaran ajan.")
    parser.add_argument("--notlar", type=Path, default=BASE_DIR / "notes", help="Not klasörü")
    parser.add_argument("--rapor", type=Path, default=BASE_DIR / "rapor.md", help="Rapor dosyası")
    parser.add_argument("--bugun", type=date.fromisoformat, default=date.today(),
                        help="Referans tarih (YYYY-AA-GG); varsayılan: bugün")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):  # Windows konsolunda Türkçe karakterler için
        sys.stdout.reconfigure(encoding="utf-8")

    report = NotesAgent(args.notlar, args.rapor, args.bugun).run()
    print("\n" + report)


if __name__ == "__main__":
    main()
