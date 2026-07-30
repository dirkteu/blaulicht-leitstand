# -*- coding: utf-8 -*-
"""
core/scoring.py  —  Drama-Score (Team 2: Ingest)
==================================================

1:1-Port der Bewertungslogik aus ranking.py (SIGNALS / DAMPENERS / CATEGORIES,
score_case, classify) als saubere, reine Text-Funktionen ohne I/O. Wird von
workers/ingest.py genutzt; core/presseportal.py und core/mail.py liefern nur
Rohdaten, die Bewertung passiert ausschliesslich hier.

    score, hits = score_case(f"{title} {text}")
    kanal       = classify(f"{title} {text}")
"""
from __future__ import annotations

import re

# --- Drama-Signale (Regex, Punkte, Label) — identisch zu ranking.py ---------
SIGNALS = [
    (r"gesprengt|sprengung|explosion|explodier|in die luft",          25, "💥 Sprengung"),
    # Kernthema des Kanals: Zigaretten-/Tabakautomat. Hebt die dramatischen
    # Automaten-Sprengungen ueber die Schwelle, ohne banalen Zigaretten-
    # Ladendiebstahl (ohne Automat) mit hochzuziehen.
    (r"zigaretten[- ]?automat|tabakautomat|zigarettenautomat",         15, "🚬 Zigarettenautomat"),
    # Zweite Kern-Nische: Geldautomaten-Sprengung. Hebt die Geldautomaten-Faelle
    # analog ueber die Schwelle (die reine „gesprengt"-Signalgebung reicht, dieser
    # Bonus macht die Nische im Score sichtbar/robust).
    (r"geldautomat|bankautomat|ec-automat|sb-terminal",                15, "🏧 Geldautomat"),
    (r"schaufenster|kracht.{0,15}(laden|gesch|schaufenster|juwel)|"
     r"(auto|pkw|wagen|mercedes).{0,20}(rammt|fuhr|kracht|schaufenster)", 25, "🚗 Schaufenster-Crash"),
    (r"messer|schusswaffe|bewaffnet|pistole|waffe|schüsse|erschoss|geschossen",
                                                                       20, "🔫 Waffe"),
    (r"maskiert|vermummt|verhüllt",                                    10, "🎭 maskiert"),
    (r"überfall|raubüberfall|raub |beraubt|ausgeraubt",                15, "💰 Raub"),
    (r"verfolgungsjagd|auf der flucht|flüchtig|entkam|entkamen|floh|"
     r"flüchtete|fliehen",                                             15, "🏃 Flucht"),
    (r"stromausfall|blackout|ohne strom|strom.{0,5}ausf",             10, "⚡ Blackout"),
    (r"serie|mehrere|erneut|wieder|in folge|tatserie",                10, "🔁 Serie"),
    (r"fehlt jede spur|zeugen gesucht|unbekannte|hinweise erbeten",   10, "❓ ungeloest"),
]

# --- Daempfer (senken den Score) — identisch zu ranking.py ------------------
DAMPENERS = [
    (r"festgenommen|gefasst|verhaftet|gestellt|geständig|ermittelt.{0,10}fest", -15, "✋ gefasst"),
    (r"versuchte|versuchter|gescheitert|erfolglos|scheiterte",                   -5, "🚫 versucht"),
    (r"portemonnaie|geldbörse|ladendiebstahl|taschendieb|fahrrad gestohlen|"
     r"einkauf gestohlen|falschparker|ruhestörung",                            -20, "🥱 Bagatelle"),
]

# --- Kategorie -> Kanal (Prioritaet von oben nach unten) — identisch --------
CATEGORIES = [
    ("Automaten-Sprengung", r"automat|zigarettenautomat|geldautomat|sprengung"),
    ("Juwelier & Crash",    r"juwelier|schmuck|goldschmied|schaufenster"),
    ("Ueberfall & Raub",    r"überfall|raub|tankstelle|supermarkt|kiosk|trinkhalle|bank"),
    ("Einbruch",            r"einbruch|einbrecher|eingebrochen"),
    ("Sonstiges",           r".*"),
]

# Schwellen (wie ranking.py) — hier zentral, damit ingest/api sie teilen koennen.
SHORT_THRESHOLD = 70          # ab hier ein eigenstaendiger Short
RESERVOIR_THRESHOLD = 40      # darunter -> verwerfen


def score_case(text: str) -> tuple[int, list[str]]:
    """Drama-Score + Liste der ausgeloesten Signale zurueckgeben.
    Port von ranking.py:score_case (SequenceMatcher-Dedup bleibt in ingest.py)."""
    t = (text or "").lower()
    score, hits = 0, []
    for pattern, pts, label in SIGNALS:
        if re.search(pattern, t):
            score += pts
            hits.append(f"{label} +{pts}")
    for pattern, pts, label in DAMPENERS:
        if re.search(pattern, t):
            score += pts
            hits.append(f"{label} {pts}")
    # Bonus fuer hohen Sachschaden (>= 10.000 EUR)
    for m in re.finditer(r"([\d.]{2,})\s*(?:euro|eur|€)", t):
        try:
            val = int(m.group(1).replace(".", ""))
            if val >= 10000:
                score += 10
                hits.append("💶 hoher Schaden +10")
                break
        except ValueError:
            pass
    return max(score, 0), hits


def classify(text: str) -> str:
    """Fall einer Kategorie/einem Kanal zuordnen (Port von ranking.py:classify)."""
    t = (text or "").lower()
    for name, pattern in CATEGORIES:
        if re.search(pattern, t):
            return name
    return "Sonstiges"
