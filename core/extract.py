# -*- coding: utf-8 -*-
"""
core/extract.py  —  Stufe 2: Fakten-Extraktion aus dem Volltext (Claude API)
=============================================================================

PORTIERT aus dem Prototyp `script_gen.py` (SYSTEM_PROMPT / call_claude_api-Muster
via urllib), gehärtet auf den make.com-Ansatz: striktes JSON exakt nach dem
Facts-Schema (core.contracts.Facts), KEINE Markdown-Fences, KEINE Namen/Adressen/
Koordinaten.

    extract_facts(fulltext, link) -> dict   # Facts.to_dict()-kompatibel
    sanitize(facts)                -> dict  # letzte Schranke, unabhängig vom Prompt

Aufrufreihenfolge (siehe workers/extract.py):
    facts = extract_facts(fulltext, link)
    facts = sanitize(facts)
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from typing import Any, Optional

from .contracts import Facts

# Für 300 Videos/Tag bewusst günstig + schnell (wie im Prototyp).
MODEL = "claude-haiku-4-5-20251001"


# ---------------------------------------------------------------------------
# PROMPT — härtet den make.com-Ansatz: striktes JSON, keine Fences, keine PII
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """Du bist Fakten-Extraktor für den deutschen Blaulicht-Leitstand.
Du bekommst den Volltext einer Polizei-Pressemeldung (Presseportal.de) und musst
daraus die sachlichen Kernfakten herausziehen, streng maschinenlesbar.

AUSGABE: AUSSCHLIESSLICH gültiges JSON, exakt nach diesem Schema — keine
Markdown-Code-Fences (kein ```), kein Kommentar davor oder danach, keine
Erklärung, kein Fließtext außerhalb des JSON:
{
  "tat": "kurze Bezeichnung der Straftat, z.B. 'Automaten-Sprengung'",
  "datum": "YYYY-MM-DD oder null, falls nicht sicher bestimmbar",
  "zeit": "HH:MM (24h) oder null, falls keine Uhrzeit im Text steht",
  "ort": "NUR die Stadt/Gemeinde, z.B. 'Dresden' — niemals Straße oder Stadtteil-Adresse",
  "taeter_anzahl": ganze Zahl oder null,
  "werkzeug": "Tatwerkzeug/Vorgehen in wenigen Worten oder null",
  "beute_eur": ganze Zahl (Euro, genannter/geschätzter Beutewert) oder null,
  "schaden_eur": ganze Zahl (Euro, Sachschaden) oder null,
  "details": "1-2 sachliche Sätze Zusammenfassung, keine wörtliche Übernahme aus dem Text",
  "ungeloest": true oder false (true, wenn Täter flüchtig/unbekannt bzw. Zeugen gesucht werden),
  "quelle_link": "wird unverändert durchgereicht, siehe unten"
}

HARTE REGELN (niemals brechen, auch wenn im Text vorhanden):
- NIEMALS Namen von Verdächtigen, Opfern oder Zeugen — auch keine Initialen.
- NIEMALS Straßennamen, Hausnummern, Postleitzahlen, Koordinaten (lat/lon).
- "ort" ausschließlich auf Stadt-/Gemeinde-Ebene, keine Stadtteile, keine Adressen.
- Keine erfundenen oder spekulativen Angaben. Unsicheres -> null bzw. weglassen.
- Zahlen als reine Ganzzahlen ohne Währungssymbol/Tausenderpunkte im JSON-Wert.
- Bei mehreren genannten Orten: die Stadt/Gemeinde des Tatorts verwenden, nicht
  die der Polizeidienststelle, falls unterscheidbar.

Gib NUR das JSON-Objekt zurück, sonst nichts."""


def build_user_prompt(fulltext: str, link: str) -> str:
    return (
        "VOLLTEXT DER PRESSEMELDUNG:\n"
        f"{fulltext}\n\n"
        f"QUELLE (unverändert als quelle_link übernehmen): {link}\n\n"
        "Extrahiere die Fakten als JSON gemäß Schema."
    )


# ---------------------------------------------------------------------------
# API-AUFRUF  (dependency-frei via urllib, wie im Prototyp)
# ---------------------------------------------------------------------------
def call_claude_api(system: str, user: str, model: str = MODEL, max_tokens: int = 700) -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY nicht gesetzt.")
    body = json.dumps({
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body,
        headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.load(resp)
    return data["content"][0]["text"]


# ---------------------------------------------------------------------------
# ROBUSTES PARSEN — ```json-Fences strippen, JSON extrahieren, Regex-Fallback
# ---------------------------------------------------------------------------
_FENCE_RE = re.compile(r"^```(json)?\s*|\s*```$", re.M)
_ZEIT_RE = re.compile(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\s*(?:uhr)?\b", re.I)
_EUR_RE = re.compile(r"(\d[\d.,]*)\s*(?:€|eur\b|euro)", re.I)


def _strip_fences(text: str) -> str:
    return _FENCE_RE.sub("", text.strip()).strip()


def _extract_json_object(text: str) -> str:
    """Fallback: erstes {...}-Objekt aus dem Text herausschneiden (falls die API
    trotz Anweisung Text drumherum liefert)."""
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1]
    return text


def _to_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        m = re.search(r"-?\d+", value.replace(".", "").replace(",", ""))
        if m:
            try:
                return int(m.group(0))
            except ValueError:
                return None
    return None


def _parse_eur_string(value: Any) -> Optional[int]:
    """Für den Fall, dass beute_eur/schaden_eur als String mit '€'/'Euro' zurückkommt."""
    if isinstance(value, str):
        m = _EUR_RE.search(value)
        if m:
            num = m.group(1).replace(".", "").replace(",", ".")
            try:
                return int(round(float(num)))
            except ValueError:
                return None
    return _to_int(value)


def _fallback_zeit(fulltext: str) -> Optional[str]:
    m = _ZEIT_RE.search(fulltext or "")
    if not m:
        return None
    return f"{int(m.group(1)):02d}:{m.group(2)}"


def _fallback_eur_pair(fulltext: str) -> tuple[Optional[int], Optional[int]]:
    """Regex-Reserve, falls Modell keine Zahlen liefert: erste zwei €-Beträge im Text."""
    hits = _EUR_RE.findall(fulltext or "")
    vals: list[int] = []
    for h in hits[:2]:
        num = h.replace(".", "").replace(",", ".")
        try:
            vals.append(int(round(float(num))))
        except ValueError:
            pass
    beute = vals[0] if len(vals) >= 1 else None
    schaden = vals[1] if len(vals) >= 2 else None
    return beute, schaden


def _parse_response(text: str, fulltext: str, link: str) -> dict[str, Any]:
    cleaned = _strip_fences(text)
    try:
        raw = json.loads(cleaned)
    except json.JSONDecodeError:
        try:
            raw = json.loads(_extract_json_object(cleaned))
        except json.JSONDecodeError:
            raw = {}
    if not isinstance(raw, dict):
        raw = {}

    facts = Facts(quelle_link=link).to_dict()
    for key in facts.keys():
        if key == "quelle_link":
            continue
        if key in raw:
            facts[key] = raw[key]

    # Typ-Härtung + Regex-Fallbacks
    facts["tat"] = str(facts.get("tat") or "").strip()
    facts["ort"] = str(facts.get("ort") or "").strip()
    facts["details"] = str(facts.get("details") or "").strip()
    facts["datum"] = facts.get("datum") or None
    facts["werkzeug"] = (str(facts["werkzeug"]).strip() or None) if facts.get("werkzeug") else None

    zeit = facts.get("zeit")
    if not zeit or not re.match(r"^\d{2}:\d{2}$", str(zeit)):
        facts["zeit"] = _fallback_zeit(fulltext)
    else:
        facts["zeit"] = zeit

    facts["taeter_anzahl"] = _to_int(facts.get("taeter_anzahl"))

    beute = _parse_eur_string(facts.get("beute_eur"))
    schaden = _parse_eur_string(facts.get("schaden_eur"))
    if beute is None and schaden is None:
        beute, schaden = _fallback_eur_pair(fulltext)
    facts["beute_eur"] = beute
    facts["schaden_eur"] = schaden

    facts["ungeloest"] = bool(facts.get("ungeloest", False))
    facts["quelle_link"] = link  # nie von der API überschreiben lassen

    return facts


# ---------------------------------------------------------------------------
# ÖFFENTLICHE FUNKTION
# ---------------------------------------------------------------------------
def extract_facts(fulltext: str, link: str) -> dict[str, Any]:
    """fulltext -> Facts-dict (core.contracts.Facts.to_dict()-kompatibel).

    Ruft die Claude API auf und parst die Antwort robust. API-/Netzwerkfehler
    werden NICHT verschluckt (der aufrufende Worker entscheidet über Retry/Error-
    Handling) — robust ist hier nur das Parsen der Modell-Antwort selbst.
    """
    fulltext = fulltext or ""
    raw_text = call_claude_api(SYSTEM_PROMPT, build_user_prompt(fulltext, link))
    return _parse_response(raw_text, fulltext, link)


# ---------------------------------------------------------------------------
# SANITIZE — letzte Datenschutz-Schranke, unabhängig vom Prompt/Modellverhalten
# ---------------------------------------------------------------------------
_STRASSE_RE = re.compile(
    r"\b[\wÄÖÜäöüß]+(?:straße|strasse|str\.|weg|gasse|allee|platz|ring)\s*\d{0,4}\b",
    re.I,
)
_PLZ_RE = re.compile(r"\b\d{5}\b")
_KOORD_RE = re.compile(r"[-+]?\d{1,3}\.\d{3,}\s*,\s*[-+]?\d{1,3}\.\d{3,}")


def sanitize(facts: dict[str, Any]) -> dict[str, Any]:
    """Letzte Schranke: verwirft alles, was nach Straße/Hausnr./PLZ/Koordinaten
    oder einem der core.contracts.Facts.VERBOTEN-Felder aussieht — unabhängig
    davon, ob Prompt/Modell schon gegriffen haben."""
    out = dict(facts)

    # Verbotene Felder dürfen im Facts-dict gar nicht existieren.
    for key in Facts.VERBOTEN:
        out.pop(key, None)

    # Ort: PLZ- und Straßen-Fragmente entfernen, nur den Stadtnamen behalten.
    ort = out.get("ort") or ""
    ort = _PLZ_RE.sub("", ort)
    ort = _STRASSE_RE.sub("", ort)
    ort = re.sub(r"\s{2,}", " ", ort).strip(" ,-")
    out["ort"] = ort

    # Details/Werkzeug/Tat: Koordinaten/PLZ/Straßen-Muster hart entfernen.
    for field_name in ("details", "werkzeug", "tat"):
        val = out.get(field_name)
        if isinstance(val, str) and val:
            val = _KOORD_RE.sub("[entfernt]", val)
            val = _PLZ_RE.sub("[entfernt]", val)
            val = _STRASSE_RE.sub("[entfernt]", val)
            out[field_name] = val.strip()

    return out
