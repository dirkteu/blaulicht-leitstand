# -*- coding: utf-8 -*-
"""
core/lektor.py  —  Sprechtexte glaetten + Lesbarkeit messen
============================================================

Zwei Dinge, beide OHNE Seiteneffekt auf die Pipeline:

    lesbarkeit(text)   -> Wiener Sachtextformel + konkrete Marker (reine Funktion)
    lektoriere(scenes) -> Umschreib-Vorschlag je Szene (EIN Claude-Aufruf)

Warum ueberhaupt: Die Voiceover-Texte sind fachlich korrekt, aber schwer hoerbar
— Schachtelsaetze, Semikolons, Wortwiederholungen, gelegentlich Tippfehler des
Modells. Regeln/Regex bekommen das nicht sauber hin, ein Sprachmodell schon.

WICHTIG — der Lektor darf die Guardrails nicht aushebeln. Jeder Vorschlag laeuft
durch dieselben Schranken wie die Extraktion (core.extract.pruefe_text) und die
Distanz-Pruefung (core.parse.distanz_fehlt). Faellt er durch, wird er VERWORFEN
und die Szene behaelt ihren Originaltext — mit sichtbarer Begruendung. Der Lektor
kann also nur besser machen, nie schlechter.

Aufgerufen ausschliesslich aus api/main.py (Button „Text glaetten" im Review).
Er laeuft NIE automatisch in der Pipeline — Umschreiben ist eine Entscheidung
des Menschen, kein stiller Schritt.
"""

from __future__ import annotations

import json
import re
from typing import Any

from . import parse
from .extract import MODEL, call_claude_api, pruefe_text


# ---------------------------------------------------------------------------
# LESBARKEIT — Wiener Sachtextformel + Marker
# ---------------------------------------------------------------------------
# Die Schulstufe allein sagt zu wenig darueber, WAS zu aendern ist. Deshalb
# zusaetzlich konkrete Marker, die direkt auf eine Textstelle zeigen.
_MAX_SATZ_WOERTER = 20        # ab hier gilt ein Satz als zu lang zum Sprechen
_MIN_WIEDERHOLUNG = 3         # ab so vielen gleichen Woertern: Wiederholung

_SATZ_RE = re.compile(r"[^.!?]+[.!?]?")
_WORT_RE = re.compile(r"[A-Za-zÄÖÜäöüß-]+")

# Fuellwoerter, die bei einer Wiederholungs-Zaehlung nicht stoeren sollen.
_STOPWOERTER = {
    "der", "die", "das", "den", "dem", "des", "ein", "eine", "einen", "einem",
    "eines", "und", "oder", "aber", "in", "im", "an", "am", "auf", "mit", "von",
    "vom", "zu", "zum", "zur", "bei", "nach", "aus", "für", "ist", "war", "sind",
    "wurde", "wurden", "sich", "es", "sie", "er", "nicht", "noch", "auch",
}


def _silben(wort: str) -> int:
    """Silben naeherungsweise ueber Vokalgruppen. Reicht fuer eine Kennzahl —
    eine echte Silbentrennung waere eine zusaetzliche Abhaengigkeit."""
    gruppen = re.findall(r"[aeiouäöüy]+", wort.lower())
    return max(1, len(gruppen))


def _saetze(text: str) -> list[str]:
    return [s.strip() for s in _SATZ_RE.findall(text or "") if s.strip()]


def lesbarkeit(text: str) -> dict[str, Any]:
    """Lesbarkeit eines Sprechtextes.

    Rueckgabe:
        stufe   float  Wiener Sachtextformel (~4 = leicht, ~15 = sehr schwer)
        ampel   str    'gut' | 'mittel' | 'schwer'
        marker  list   konkrete Befunde als Klartext
    """
    t = (text or "").strip()
    saetze = _saetze(t)
    woerter = _WORT_RE.findall(t)
    if not saetze or not woerter:
        return {"stufe": 0.0, "ampel": "gut", "marker": []}

    n = len(woerter)
    ms = 100 * sum(1 for w in woerter if _silben(w) >= 3) / n   # % vielsilbig
    sl = n / len(saetze)                                         # mittlere Satzlaenge
    iw = 100 * sum(1 for w in woerter if len(w) > 6) / n         # % lange Woerter
    es = 100 * sum(1 for w in woerter if _silben(w) == 1) / n    # % einsilbig
    stufe = 0.1935 * ms + 0.1672 * sl + 0.1297 * iw - 0.0327 * es - 0.875

    marker: list[str] = []
    for s in saetze:
        anzahl = len(_WORT_RE.findall(s))
        if anzahl > _MAX_SATZ_WOERTER:
            marker.append(f"Satz mit {anzahl} Wörtern (zum Sprechen zu lang)")
        if s.count(",") >= 2:
            marker.append("Satz mit mehreren Nebensätzen")
    if ";" in t:
        marker.append("Semikolon — im gesprochenen Text unhörbar")

    haeufig: dict[str, int] = {}
    for w in woerter:
        wl = w.lower()
        if wl not in _STOPWOERTER and len(wl) > 3:
            haeufig[wl] = haeufig.get(wl, 0) + 1
    for wort, anzahl in haeufig.items():
        if anzahl >= _MIN_WIEDERHOLUNG:
            marker.append(f'„{wort}“ {anzahl}× wiederholt')

    ampel = "gut" if stufe <= 8 else ("mittel" if stufe <= 11 else "schwer")
    return {"stufe": round(stufe, 1), "ampel": ampel, "marker": marker}


# ---------------------------------------------------------------------------
# LEKTOR — Umschreiben auf Sprechbarkeit
# ---------------------------------------------------------------------------
LEKTOR_SYSTEM = """Du bist Lektor für gesprochene True-Crime-Kurzvideos auf Deutsch.
Du bekommst die Sprechtexte einzelner Szenen und schreibst sie so um, dass eine
Sprecherstimme sie flüssig vorlesen kann und Zuhörer sie sofort verstehen.

SO SCHREIBST DU UM:
- Kurze Hauptsätze. Ein Gedanke pro Satz. Höchstens etwa 20 Wörter.
- Keine Schachtelsätze, keine angehängten Relativsatz-Ketten. Lieber zwei Sätze.
- Kein Semikolon — im gesprochenen Text ist es nicht hörbar.
- Wortwiederholungen auflösen, aber nicht auf Kosten der Klarheit.
- Offensichtliche Tippfehler und Grammatikfehler korrigieren.
- STRAFFEN IST ERLAUBT: Nebensächliches darf ganz wegfallen.

DAS MUSS ERHALTEN BLEIBEN (Kernfakten, niemals streichen):
Ort, Uhrzeit, Art der Tat, Beute, Schaden, Stand der Fahndung.

HARTE REGELN (wichtiger als jede Stilfrage):
1. UNSCHULDSVERMUTUNG: Jeder Satz, in dem MENSCHEN etwas TUN, bleibt
   distanziert — "sollen ... haben/sein", "mutmaßlich" oder "angeblich".
   Steht das im Original, muss es auch in deiner Fassung stehen. Das Wort
   "unbekannt" allein reicht NICHT.
   FALSCH: "Zwei unbekannte Täter sprengten den Automaten."
   RICHTIG: "Zwei unbekannte Täter sollen den Automaten gesprengt haben."
   Sätze ohne handelnde Personen bleiben normal: "Der Automat wurde zerstört."
2. KEINE NACHAHMUNGS-ANLEITUNG: Die Tat darf benannt werden ("gesprengt",
   "Explosion", "Sprengsatz"). Das WIE niemals — keine Stoffarten, Mengen,
   Zuführung, Zündung.
3. KEINE NAMEN, STRASSEN, HAUSNUMMERN, POSTLEITZAHLEN, KOORDINATEN.
4. KEINE NEUEN FAKTEN. Du darfst umformulieren und weglassen — niemals etwas
   hinzuerfinden, ausschmücken oder vermuten.

AUSGABE: ausschließlich gültiges JSON, keine Code-Fences, kein Text davor oder
danach:
{"szenen": [{"i": 0, "vo": "neuer Text"}, {"i": 1, "vo": "neuer Text"}]}
Gib jede Szene genau einmal zurück, mit ihrem Index aus der Eingabe."""


def _json_aus_antwort(raw: str) -> dict[str, Any]:
    """JSON aus der Modellantwort holen, auch wenn doch Code-Fences drumstehen."""
    t = (raw or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    start, ende = t.find("{"), t.rfind("}")
    if start == -1 or ende == -1:
        raise ValueError(f"Keine JSON-Antwort vom Lektor: {t[:200]}")
    return json.loads(t[start:ende + 1])


def lektoriere(scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Umschreib-Vorschlag je Szene, bereits guardrail-geprueft.

    Ein einziger Claude-Aufruf fuer ALLE Szenen — billiger, und der Lektor sieht
    den Zusammenhang (er kann z. B. eine Wortwiederholung ueber Szenengrenzen
    hinweg aufloesen).

    Rueckgabe je Szene:
        i, role, alt, neu, uebernommen (bool), grund (str),
        lesbarkeit_alt, lesbarkeit_neu
    Bei uebernommen=False steht in `neu` der Originaltext und in `grund`, warum
    der Vorschlag verworfen wurde.
    """
    eingabe = [{"i": i, "role": s.get("role", ""), "vo": (s.get("vo") or "").strip()}
               for i, s in enumerate(scenes)]

    roh = call_claude_api(
        LEKTOR_SYSTEM,
        json.dumps({"szenen": eingabe}, ensure_ascii=False),
        model=MODEL,
        max_tokens=1500,
    )
    vorschlaege = {int(s["i"]): str(s.get("vo") or "").strip()
                   for s in _json_aus_antwort(roh).get("szenen", [])
                   if s.get("i") is not None}

    ergebnis: list[dict[str, Any]] = []
    for i, s in enumerate(scenes):
        alt = (s.get("vo") or "").strip()
        neu = vorschlaege.get(i, "")
        uebernommen, grund = True, ""

        if not neu:
            uebernommen, grund = False, "Lektor hat für diese Szene nichts geliefert."
        elif neu == alt:
            uebernommen, grund = False, "Unverändert — hier war nichts zu glätten."
        else:
            verstoesse = pruefe_text(neu)
            if verstoesse:
                uebernommen, grund = False, "Verworfen: " + ", ".join(verstoesse)
            # Distanz darf nicht wegformuliert werden — aber nur pruefen, wenn
            # das Original sie ueberhaupt hatte (sonst gaebe es nichts zu verlieren).
            elif not parse.distanz_fehlt(alt) and parse.distanz_fehlt(neu):
                uebernommen, grund = False, "Verworfen: Unschuldsvermutung ginge verloren"

        ergebnis.append({
            "i": i,
            "role": s.get("role", ""),
            "alt": alt,
            "neu": neu if uebernommen else alt,
            "uebernommen": uebernommen,
            "grund": grund,
            "lesbarkeit_alt": lesbarkeit(alt),
            "lesbarkeit_neu": lesbarkeit(neu if uebernommen else alt),
        })
    return ergebnis
