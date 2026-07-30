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

from . import parse
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
  "werkzeug": "grobe Werkzeug-KATEGORIE als Gegenstand, passend in den Satz 'Mit ... sollen die Täter vorgegangen sein' — z.B. 'einem Sprengsatz', 'einem Winkelschleifer', 'schwerem Aufbruchwerkzeug'. Niemals das WIE, niemals ein Vorgang wie 'Sprengung'. null, wenn unklar",
  "beute_eur": ganze Zahl (Euro, genannter/geschätzter Beutewert) oder null,
  "schaden_eur": ganze Zahl (Euro, Sachschaden) oder null,
  "details": "2-4 kurze, sachliche Sätze Zusammenfassung zum VORLESEN, keine wörtliche Übernahme aus dem Text (Form siehe SPRECHBARKEIT)",
  "ungeloest": true oder false (true, wenn Täter flüchtig/unbekannt bzw. Zeugen gesucht werden),
  "quelle_link": "wird unverändert durchgereicht, siehe unten"
}

SPRECHBARKEIT von "details" — der Text wird von einer Stimme VORGELESEN, nicht
gelesen. Der Zuhörer kann nicht zurückspringen:
- Kurze Hauptsätze, ein Gedanke pro Satz, höchstens etwa 20 Wörter.
- KEIN Semikolon und KEIN Gedankenstrich — beides ist beim Hören nicht wahrnehmbar.
  Mach daraus zwei Sätze.
- Keine angehängten Relativsatz-Ketten. Statt "…flüchteten mit einem Auto, das
  später in Amsterdam verwickelt wurde" lieber: "…flüchteten mit einem Auto.
  Dieses Fahrzeug soll später in Amsterdam aufgetaucht sein."
- Lieber drei kurze Sätze als einen langen. Die Konjunktiv-Pflicht unten gilt
  trotzdem in JEDEM dieser Sätze.

HARTE REGELN (niemals brechen, auch wenn im Text vorhanden):
- NIEMALS Namen von Verdächtigen, Opfern oder Zeugen — auch keine Initialen.
- NIEMALS Straßennamen, Hausnummern, Postleitzahlen, Koordinaten (lat/lon).
- "ort" ausschließlich auf Stadt-/Gemeinde-Ebene, keine Stadtteile, keine Adressen.
- Keine erfundenen oder spekulativen Angaben. Unsicheres -> null bzw. weglassen.
- Zahlen als reine Ganzzahlen ohne Währungssymbol/Tausenderpunkte im JSON-Wert.
- Bei mehreren genannten Orten: die Stadt/Gemeinde des Tatorts verwenden, nicht
  die der Polizeidienststelle, falls unterscheidbar.
- UNSCHULDSVERMUTUNG in "details" — die wichtigste Sprachregel, wörtlich befolgen:
  Die Unschuldsvermutung schützt PERSONEN, nicht EREIGNISSE. Daraus folgen zwei
  verschiedene Dinge — verwechsle sie nicht:

  (A) DIE TAT SELBST ist eine Tatsache, wenn die Polizei sie meldet. Dass ein
      Automat gesprengt wurde, steht nicht in Frage — der Automat ist zerstört.
      Schreib das im INDIKATIV: "Ein Geldautomat wurde gesprengt."

  (B) DIE TÄTERSCHAFT ist das, was unbewiesen sein kann. Hier entscheidet, ob
      jemand IDENTIFIZIERT ist:

      • Täter UNBEKANNT oder flüchtig (niemand ist festgenommen oder benannt):
        Dann gibt es keine Person, die vorverurteilt werden könnte. INDIKATIV
        ist richtig und erwünscht — genau so schreiben Polizei und Presse:
          RICHTIG: "Unbekannte Täter sprengten den Automaten und flüchteten."
          RICHTIG: "Die Täter sind flüchtig, die Fahndung läuft."
        Setze hier KEINEN Konjunktiv — das klingt vorsichtiger als die Quelle
        und ist sachlich unnötig.

      • Sobald jemand IDENTIFIZIERT ist — festgenommen, beschuldigt, benannt
        ("der 24-Jährige", "die Festgenommenen", "Tatverdächtige"): Dann greift
        die Unschuldsvermutung mit voller Wucht. Distanz ist PFLICHT:
          FALSCH: "Der Festgenommene sprengte den Automaten."
          RICHTIG: "Der Festgenommene soll den Automaten gesprengt haben."

      • Ist der HERGANG selbst unsicher (nur Zeugenangaben, widersprüchliche
        Darstellung, Vermutung der Ermittler), distanziere ebenfalls — dann aber
        wegen der unsicheren Quelle, nicht wegen der Schuld:
          "Nach Angaben von Zeugen flohen zwei Männer auf Fahrrädern."

  Wenn du distanzierst, WECHSLE DIE MITTEL AB. "sollen" höchstens EINMAL im
  ganzen details-Text, und nie in zwei aufeinanderfolgenden Sätzen dasselbe
  Mittel — dreimal "sollen" hintereinander liest sich wie ein Formular.
  Zur Auswahl stehen:
    a) Konjunktiv I der indirekten Rede (die eleganteste Form):
       "Die Täter hätten den Automaten gesprengt." / "Sie seien geflüchtet."
    b) "sollen ... haben/sein"  (sparsam einsetzen)
    c) "mutmaßlich" / "die mutmaßlichen Täter" / "Tatverdächtige"
    d) Quellenzuschreibung: "laut Polizei", "nach Angaben der Ermittler",
       "den Ermittlern zufolge", "nach bisherigen Erkenntnissen"
    e) "angeblich", "offenbar"
    f) AM BESTEN, wo es passt: Satz ganz OHNE handelnde Person. Ohne
       Täter-Subjekt gibt es nichts zu behaupten und nichts zu distanzieren:
       "Der Geldautomat wurde gesprengt." statt "Die Täter sollen ... haben."
  Beispiel für einen Fall mit UNBEKANNTEN Tätern (Indikativ, so wie die Quelle):
    "In einer Bankfiliale wurde am frühen Dienstagmorgen ein Geldautomat
     gesprengt. Die unbekannten Täter flüchteten ohne Beute. Das Wohnhaus wurde
     erheblich beschädigt, ist aber nicht einsturzgefährdet. Nach Angaben von
     Zeugen flohen zwei Männer auf Fahrrädern."
  Beispiel für einen Fall mit IDENTIFIZIERTEM Beschuldigten (Distanz Pflicht,
  Mittel abgewechselt):
    "Ein Geldautomat wurde gesprengt. Ein 24-Jähriger soll die Tat begangen
     haben. Er sei kurz darauf festgenommen worden. Der Schaden liegt im
     sechsstelligen Bereich."
  Wenn du den Konjunktiv nutzt, gilt er bis zum Satzende — auch in angehängten
  Teilsätzen nach "und". Er darf nicht auf halbem Weg zurückfallen:
    FALSCH: "Er soll Geldkassetten mitgenommen und ist mit dem Rad geflohen."
    RICHTIG: "Er soll Geldkassetten mitgenommen haben und mit dem Rad
             geflohen sein."
  Sätze OHNE handelnde Personen sind IMMER Indikativ — Schäden, Sachen,
  Behörden-Handeln sind keine Schuldbehauptung:
    OK: "Der Automat wurde vollständig zerstört."
    OK: "Die Fahndung mit Hubschrauber blieb erfolglos."
  Solange niemand verurteilt ist, gilt jede identifizierte Person als unschuldig.
- KEINE NACHAHMUNGS-ANLEITUNG in "werkzeug", "details" und "tat": Die Tat DARF
  benannt werden (z.B. "gesprengt", "Sprengung", "Explosion", "Winkelschleifer",
  "Aufbruchwerkzeug") — das WIE aber NIEMALS. Verboten sind konkrete Stoffarten
  (z.B. Gasgemisch, Butan, Propan, Schwarzpulver), Mengenangaben, die Art der
  Zuführung (z.B. "über einen Schlauch eingeleitet"), Zündmechanismen und jede
  Schritt-für-Schritt-Abfolge. Im Zweifel die Kategorie nennen und das Wie
  weglassen — der Fokus liegt auf Tatort, Schaden, Folgen und Fahndung.

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

# Sammelmuster fuer die satzweise Schranke in den gesprochenen Feldern.
_PII_RE = re.compile(
    "|".join(f"(?:{p.pattern})" for p in (_KOORD_RE, _PLZ_RE, _STRASSE_RE)),
    re.I,
)


def pruefe_text(text: str) -> list[str]:
    """Verstoesse eines Textes gegen die harten Schranken, im Klartext.

    Leere Liste = sauber. Genutzt von core.lektor, um Lektor-Vorschlaege
    nachzukontrollieren: ein umgeschriebener Text darf die Guardrails nicht
    wieder hereinschreiben, die sanitize() bei der Extraktion entfernt hat.
    """
    gruende: list[str] = []
    t = text or ""
    if _KOORD_RE.search(t) or _PLZ_RE.search(t) or _STRASSE_RE.search(t):
        gruende.append("Adresse/PLZ/Koordinaten")
    if parse.hat_methode(t):
        gruende.append("Methoden-Detail (Nachahmungs-Schutz)")
    return gruende


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

    # Details/Werkzeug/Tat: Saetze mit Adress-/Koordinaten-Resten ODER mit
    # Methoden-/Anleitungs-Details komplett streichen.
    #
    # Frueher wurden hier "[entfernt]"-Platzhalter eingesetzt — diese Felder
    # landen aber im Voiceover, und die TTS liest den Platzhalter woertlich vor
    # ("eckige Klammer entfernt"). Deshalb faellt jetzt der ganze Satz weg,
    # siehe core.parse.drop_saetze.
    for field_name in ("details", "werkzeug", "tat"):
        val = out.get(field_name)
        if isinstance(val, str) and val:
            val = parse.drop_saetze(val, _PII_RE)
            out[field_name] = parse.entschaerfe_methode(val)

    # Leer gewordenes werkzeug -> None, damit core.script die Zeile weglaesst
    # statt "Mit  sollen die Taeter vorgegangen sein" zu bauen.
    if not (out.get("werkzeug") or "").strip():
        out["werkzeug"] = None

    return out
