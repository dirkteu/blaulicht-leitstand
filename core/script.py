# -*- coding: utf-8 -*-
"""
core/script.py  —  Stufe 3: Fakten -> Video-Bauanleitung (spec)
=================================================================

PORTIERT `assemble_spec` + `pick_broll` aus dem Prototyp `script_gen.py`,
speist aber echte Fakten (core.contracts.Facts) statt eines Claude-generierten
Zwischen-„script" ein:

    - echte Uhrzeit im Hook
    - Werkzeug in der Story-Szene
    - Beute/Schaden in der Zahlen-Szene
    - ungelöst-Status im Cliffhanger

    build_spec(case, facts) -> spec   # 5 Szenen: hook, eskalation, story, zahlen, cliffhanger

Deterministisch: B-Roll-Wahl hängt nur vom Titel/Link ab (hashlib.md5-Seed),
damit derselbe Fall bei erneutem Lauf dieselbe Bauanleitung erhält.
"""

from __future__ import annotations

import hashlib
import random
import re
from datetime import datetime
from typing import Any, Optional

from . import parse

CHANNEL = "Nachtknall"
DURATION = 42  # Ziel-Länge in Sekunden (Richtwert, siehe durs unten)

# Steht unter jeder Video-Beschreibung (workers/publish.py baut sie aus
# spec.meta.caption). Signalisiert der Plattform-Moderation Dokumentation statt
# Verherrlichung — das ist die Achse, auf der TikTok/YouTube tatsaechlich
# pruefen. Deckt zugleich die Unschuldsvermutung nach aussen ab.
DISCLAIMER = (
    "Hinweis: Dieser Kanal dokumentiert Kriminalfälle sachlich auf Basis "
    "offizieller Polizeimeldungen und Medienberichte. Es gilt die "
    "Unschuldsvermutung. Nachahmung ist strafbar."
)

# ---------------------------------------------------------------------------
# B-ROLL-BIBLIOTHEK — PORTIERT aus script_gen.py (Dateinamen wie im Bucket `broll`)
# ---------------------------------------------------------------------------
# POOL-GROESSE: die obere Grenze je Zeile muss zu den Dateien im Bucket passen.
# Namen bleiben broll_<kategorie>_NN.mp4; der Picker waehlt deterministisch per
# Hash, damit derselbe Fall immer dieselben Clips bekommt.
#
# Die effekt-Clips 02-10 stammen aus VIER realen Tatorten (Zuordnung:
# PROJEKTBUCH_BROLL.md, Abschnitt 7). Innerhalb eines Videos darf nur EIN
# Tatort vorkommen — zwei verschiedene Automaten in einem Clip zerstoeren
# genau die Konsistenz, fuer die das Master-Verfahren gebaut wurde
# (BROLL_PLAN Beschluss 5: Vielfalt nur ueber komplette Saetze, „nie ueber
# Einzelclip-Wuerfeln"). Die Zuteilung waehlt deshalb je Video EINEN Satz.
#
# broll_effekt_01.mp4 bleibt bewusst draussen: der GENERIERTE Clip vom
# 26.07. zeigt einen fremden Automaten und passt zu keinem Satz.
EFFEKT_SAETZE = [
    ["broll_effekt_02.mp4", "broll_effekt_03.mp4", "broll_effekt_07.mp4"],  # Wrack 1 (Pfosten)
    ["broll_effekt_04.mp4", "broll_effekt_05.mp4"],                          # VISA-Automat
    ["broll_effekt_06.mp4", "broll_effekt_08.mp4"],                          # Wandautomat
    ["broll_effekt_09.mp4", "broll_effekt_10.mp4"],                          # Tobaccoland am Zaun
]

# `cctv` als EXPLIZITE Liste statt als range() — wie EFFEKT_SAETZE. Ein
# Rauswurf ist dann eine gestrichene Zeile, und man sieht im Code, welches
# Motiv gemeint ist. broll_cctv_01.mp4 (26.07.) bleibt draussen: zeigt den
# INTAKTEN Automaten, verstoesst gegen BROLL_PLAN Beschluss 2/3 (nur
# kulisse/effekt zeigen den Automaten).
#
# ⚠ SICHTUNG OFFEN (03.08.2026): Diese sechs stammen aus der Runde vom 01.08.,
# die noch mit der alten Whitelist-Textregel lief — also mit genau dem Fehler,
# der bei broll_prompts.TEXT_REGEL_SZENE dokumentiert ist ("ACHTUNG ab 18" als
# Bauzaun-Plakat, "POLIZAI"/"ACHEUT" als Laden-Schriftzuege). Der Upload kam
# VOR dem Befund (git: bb9dfbf, dann 8902d96), ein Rollback des Pools nie.
# Was bei der Sichtung durchfaellt, wird hier gestrichen.
# Motiv-Zuordnung laut BROLL_PLAN.md — bei der Sichtung bestaetigen.
CCTV_CLIPS = [
    "broll_cctv_02.mp4",   # Taeter-Vorfahrt
    "broll_cctv_03.mp4",   # Taeter rennt
    "broll_cctv_04.mp4",   # Taeter-Gestalten mit Beutetasche
    "broll_cctv_05.mp4",   # Flucht-Roller
    "broll_cctv_06.mp4",   # Fluchtwagen
    "broll_cctv_07.mp4",   # leere Strasse (ungeloest)
]

# Die uebrigen Kategorien stehen weiter auf 1 — dort liegt je ein Clip.
# `weather` gestrichen per BROLL_PLAN Beschluss 1 (umgesetzt 01.08.2026).
ASSETS = {
    "street":    [f"broll_strasse_{i:02d}.mp4"   for i in range(1, 2)],
    "blaulicht": [f"broll_blaulicht_{i:02d}.mp4" for i in range(1, 2)],
    "cctv":      list(CCTV_CLIPS),
    "location":  [f"broll_kulisse_{i:02d}.mp4"   for i in range(1, 2)],
    "effect":    [clip for satz in EFFEKT_SAETZE for clip in satz],
}

# Welche B-Roll-Kategorie passt zu welcher Szenen-Rolle.
#
# VIER-TEILE-KLAMMER (UEBERLEGUNG_DRAMATURGIE.md, umgesetzt 01.08.2026):
# Teil 1 Polizei (hook) → Teil 2 die Tat/der Automat (eskalation) →
# Teil 3 Taeter & Flucht (story + zahlen) → Teil 4 wieder der Automat
# (cliffhanger, letztes Bild). Der Clip endet beim zerstoerten Automaten
# unter „ungeloest", nicht beim wegfahrenden Auto.
# `location` (intakter Automat) und `weather` haengen damit an keiner Rolle
# mehr — das fehlende Foto des intakten Automaten blockiert nichts.
# `cctv` traegt Teil 3 und ist laut BROLL_PLAN Beschluss 3 neu definiert
# (Taeter-Silhouetten/Fluchtfahrzeug OHNE Automat) — Pool siehe CCTV_CLIPS.
ROLE_BROLL = {
    "hook":        "blaulicht",
    "eskalation":  "effect",
    "story":       "cctv",
    "zahlen":      "cctv",
    "cliffhanger": "effect",
}

# Feste Szenen-Dauern (Summe ~ DURATION), wie im Prototyp
SCENE_ORDER = ("hook", "eskalation", "story", "zahlen", "cliffhanger")
SCENE_DURATIONS = {"hook": 3, "eskalation": 7, "story": 18, "zahlen": 8, "cliffhanger": 6}
SCENE_SFX = {"hook": "boom", "eskalation": "sirene", "story": "herzschlag",
             "zahlen": "herzschlag", "cliffhanger": "stille"}

# Zielabstand zwischen zwei Schnitten. Die Bildanzahl je Abschnitt wird daraus
# berechnet, statt in einer Tabelle zu stehen.
#
# Vorher war es eine feste Tabelle (hook 1, eskalation 2, story 4, zahlen 2,
# cliffhanger 1), kalibriert auf die alten Soll-Dauern. Seit die Abschnitte ihre
# Laenge aus dem gesprochenen Text ziehen, passte sie nicht mehr: Am Fall Glinde
# schnitt die 5,5-s-Story viermal (1,4 s je Bild), waehrend der 13-s-Schluss auf
# einem einzigen Standbild stand.
SEK_PRO_BILD = 5.0
MAX_BILDER = 4
# Der Schluss traegt die Klammer und soll ruhig sein — aber nicht erstarren.
# Zwei bis drei Einstellungen desselben Motivs (Nutzer-Entscheid 03.08.2026).
CLIFFHANGER_BILDER = (2, 3)


def _sekunden(text: str) -> float:
    """Grobe Sprechdauer eines Textes. Die echte misst spaeter `tts.synth()`;
    hier reicht die Schaetzung, weil nur die Bildanzahl daran haengt."""
    return len(text or "") / ZEICHEN_PRO_SEKUNDE + 0.35   # + Atempause, s. tts.GAP


def _bildanzahl(rolle: str, sekunden: float) -> int:
    """Wie viele verschiedene Bilder ein Abschnitt zeigt."""
    n = max(1, round(sekunden / SEK_PRO_BILD))
    if rolle == "cliffhanger":
        lo, hi = CLIFFHANGER_BILDER
        return max(lo, min(hi, n))
    return min(MAX_BILDER, n)


# WELCHE BILDSORTE ZU WELCHEM SATZ — nach Inhalt, nicht nach Abschnittsnamen.
#
# Bis 03.08.2026 hing die Bildsorte allein am Rollennamen (ROLE_BROLL). Das war
# auf die alte Satzverteilung kalibriert; seit die Saetze einen Abschnitt nach
# vorn rutschen, kippte die Zuordnung ins GEGENTEIL. Belegt am Fall Glinde:
# „…auf Fahrraedern die Flucht ergriffen" lief ueber Bildern des zerstoerten
# Automaten, waehrend „Der Geldautomat wurde vollstaendig zerstoert" Fluchtwagen
# und Flucht-Roller zeigte.
#
# `hook` und `cliffhanger` bleiben fest verdrahtet: Sie tragen die Klammer
# (Polizei am Anfang, Tatobjekt als letztes Bild) und sollen sich nicht nach
# dem Wortlaut richten.
#
# Die Muster stehen hier und nicht in core.parse, weil sie auf die
# B-Roll-Kategorien abbilden — das ist die Zustaendigkeit dieses Moduls. In
# parse.py wohnen nur die Regeln, die sich core.lektor mit uns teilt.
_FLUCHT_RE = re.compile(
    r"\bflucht\w*|\bfl[üu]cht\w*|\bfloh(?:en)?\b|\bentkam\w*"
    r"|\bfahrrad\w*|\brad\b|\broller\b|\bmoped\b|\bfahrzeug\w*|\bauto\b|\bpkw\b"
    r"|\bt[äa]ter\w*|\bm[äa]nner\b|\bpersonen\b|\bunbekannte\w*|\bzeugen\b",
    re.I,
)
_OBJEKT_RE = re.compile(
    r"\bautomat\w*|\bgespreng\w*|\bsprengung\w*|\bzerst[öo]r\w*|\bbesch[äa]dig\w*"
    r"|\bschaden\w*|\bgeb[äa]ude\w*|\bwohnhaus\w*|\bfiliale\w*|\bexplosion\w*"
    r"|\btr[üu]mmer\w*|\baufgebroch\w*|\bkassette\w*",
    re.I,
)


def _bild_kategorie(rolle: str, text: str) -> str:
    """Bildsorte eines Abschnitts — aus dem Inhalt, wo es sinnvoll ist."""
    fest = ROLE_BROLL.get(rolle, "street")
    if rolle not in ("eskalation", "story"):
        return fest
    flucht = len(_FLUCHT_RE.findall(text or ""))
    objekt = len(_OBJEKT_RE.findall(text or ""))
    if flucht > objekt:
        return "cctv"
    if objekt > flucht:
        return "effect"
    return fest   # Gleichstand: bei der bisherigen Zuordnung bleiben

# ZIEL-LAENGEN je Abschnitt. Die Dauer laesst sich nicht direkt stellen:
# `tts.synth()` misst den gesprochenen Text und schreibt die Zeiten zurueck.
# Kuerzer wird ein Abschnitt also nur, indem er weniger zu sagen bekommt.
#
# Gezaehlt wird in ZEICHEN, nicht in Saetzen. Ein Deckel auf die Satzzahl
# reicht nicht: deutsche Polizeimeldungen haben Saetze von 40 bis 200 Zeichen.
# Belegt am 03.08.2026 — mit „hoechstens zwei Saetze" wuchs die Story beim Fall
# Fuerth auf 20,3 s (zwei sehr lange Saetze), waehrend sie bei Fachbach mit
# drei kurzen bei 9 s lag.
ZEICHEN_PRO_SEKUNDE = 13.2   # gemessen an den 5 vertonten Faellen, 03.08.2026
BUDGET_SEK = {"hook": 8, "eskalation": 8, "story": 12, "cliffhanger": 11}


def _budget(rolle: str) -> int:
    """Zeichen-Budget eines Abschnitts."""
    return int(BUDGET_SEK[rolle] * ZEICHEN_PRO_SEKUNDE)


def _fuellen(saetze: list[str], budget: int) -> tuple[str, list[str]]:
    """Saetze bis zum Budget entnehmen; gibt (Text, uebrige Saetze) zurueck.

    Der ERSTE Satz wird immer genommen, auch wenn er das Budget sprengt: Saetze
    lassen sich nicht gefahrlos zerteilen, und ein leerer Abschnitt waere
    schlechter als ein zu langer. Ab dem zweiten Satz gilt das Budget hart.
    """
    genommen: list[str] = []
    laenge = 0
    for s in saetze:
        if genommen and laenge + len(s) > budget:
            break
        genommen.append(s)
        laenge += len(s) + 1
    return " ".join(genommen), saetze[len(genommen):]


def broll_zuteilung(seed: int, plan: list[tuple[str, str, int]]) -> dict[str, list[str]]:
    """Clips fuer ALLE Szenen eines Videos in einem Zug waehlen.

    Je Kategorie wird der Pool mit dem Fall-Seed gemischt und dann OHNE
    Zuruecklegen ausgegeben: Zwei Szenen derselben Kategorie koennen
    denselben Clip erst bekommen, wenn der Pool erschoepft ist (dann wird
    von vorn durchgereicht — bei den Ein-Clip-Kategorien unvermeidlich).
    Deterministisch: derselbe Fall bekommt stabil dieselben Clips.

    Ersetzt pick_broll(role, seed+t): dessen Index kollidierte modulo
    Poolgroesse — die Szenenstarts 10 (story) und 28 (zahlen) landeten bei
    9 Clips beide auf Index 1, hook (0) und cliffhanger (36) beide auf 0.

    `plan` ist die Liste (Rolle, Bildkategorie, Anzahl) — sie kommt aus
    `build_spec()`, weil beides dort vom Text abhaengt: welche Abschnitte es
    ueberhaupt gibt, welche Bildsorte zum Satz passt und wie viele Bilder in
    die gesprochene Dauer passen.
    """
    rnd = random.Random(seed)
    gemischt = {kat: rnd.sample(pool, len(pool)) for kat, pool in ASSETS.items()}
    # effekt: EIN Tatort-Satz je Video (siehe EFFEKT_SAETZE). Braucht ein
    # Video mehr Automaten-Clips, als der Satz hergibt, wird innerhalb des
    # Satzes von vorn durchgereicht — der Cliffhanger kehrt dann woertlich
    # zum Eskalations-Bild zurueck, was die Klammer eher staerkt als stoert.
    satz = rnd.choice(EFFEKT_SAETZE)
    gemischt["effect"] = rnd.sample(satz, len(satz))
    vergeben = {kat: 0 for kat in ASSETS}
    zuteilung: dict[str, list[str]] = {}
    for role, kat, n in plan:
        pool = gemischt[kat]
        zuteilung[role] = [pool[(vergeben[kat] + i) % len(pool)] for i in range(n)]
        vergeben[kat] += n
    return zuteilung


# ---------------------------------------------------------------------------
# SZENEN-TEXTE — aus echten Fakten gebaut (keine Titel-Keyword-Heuristik mehr)
# ---------------------------------------------------------------------------
def _line_hook(ort: str, zeit: Optional[str], tat: str,
               kernsatz: str = "", schaden: Optional[int] = None) -> str:
    """Einstieg: staerkster Fakt zuerst, Ort und Zeit danach.

    Die ersten Sekunden entscheiden, ob jemand weiterschaut. Bis zum 03.08.2026
    stand hier ein Etikett („Um 04:30 Uhr in Glinde: Automaten-Sprengung.") —
    Ort und Uhrzeit sind aber das Uninteressanteste, was eine Meldung hergibt,
    und der Abschnitt war mit 4,6 s zugleich der kuerzeste des Clips.

    Rangfolge des staerksten Fakts, der Reihe nach durchprobiert:
      1. der erste Satz aus `details` — er nennt Tatobjekt und Umstand
      2. die Schadenshoehe, wenn bekannt
      3. `tat` schlicht benannt
    Danach ein kurzer Ortsstempel. Der Abschnitt wird dadurch laenger UND
    staerker; das ist dieselbe Aenderung, nicht zwei.
    """
    stempel = f"{ort}, {zeit} Uhr." if zeit else f"{ort}, mitten in der Nacht."

    kern = (kernsatz or "").strip()
    if kern:
        return f"{kern.rstrip('.')}. {stempel}"
    # Hier bewusst Truthiness statt `is not None` (anders als in _line_zahlen):
    # „Sachschaden rund 0 Euro" waere als Aufhaenger unsinnig, ein Schaden von 0
    # soll den Einstieg also gar nicht erst tragen.
    if schaden:
        return f"{tat or 'Ein Vorfall'} — Sachschaden rund {_eur(schaden)} Euro. {stempel}"
    return f"{tat or 'Ein Einsatz, der die Polizei auf den Plan ruft'}. {stempel}"


def _split_sentences(details: str) -> list[str]:
    if not details:
        return []
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", details) if s.strip()]


def _taeter(ungeloest: bool) -> str:
    """Unschuldsvermutung: nie schuld-behauptend. Bei flüchtigen/unbekannten
    Tätern 'die unbekannten Täter', sonst 'die mutmaßlichen Täter'."""
    return "die unbekannten Täter" if ungeloest else "die mutmaßlichen Täter"


def _line_eskalation(tat: str, first_sentence: str) -> str:
    if first_sentence:
        return first_sentence.rstrip(".") + "."
    # Ohne .lower(): `tat` ist ein Substantiv („Automaten-Sprengung") und wird
    # im Deutschen grossgeschrieben. Der Notnagel griff frueher selten; seit die
    # Saetze einen Abschnitt nach vorn rutschen, faellt „sprengung sorgt fuer
    # einen Grosseinsatz" oefter an.
    return f"Die Lage eskaliert schnell — {(tat or 'der Vorfall').strip()} sorgt für einen Großeinsatz."


def _werkzeug_satz(werkzeug: Optional[str], ungeloest: bool,
                   distanz_vorhanden: bool = False) -> str:
    """Der Werkzeug-Satz, mit dem die Story oeffnet.

    Seit 03.08.2026 eigenstaendig, damit `build_spec()` seine Laenge vom
    Story-Budget abziehen kann, bevor es Fakten-Saetze auffuellt.

    Die Unschuldsvermutung schuetzt PERSONEN, nicht Ereignisse — und greift erst,
    sobald jemand identifiziert ist. Deshalb drei Varianten:

    - `ungeloest=True` (Taeter unbekannt/fluechtig): INDIKATIV. Es gibt keine
      Person, die vorverurteilt werden koennte; Polizei und Presse schreiben an
      dieser Stelle selbst im Indikativ.
    - `ungeloest=False` (jemand gefasst/benannt) + `distanz_vorhanden=False`:
      Der Satz traegt die Distanzierung selbst („sollen ... vorgegangen sein").
    - `ungeloest=False` + `distanz_vorhanden=True` (`details` distanziert schon):
      agentloses Passiv, damit sich „sollen" nicht stapelt.
    """
    if not werkzeug:
        return ""
    if ungeloest:
        return f"Mit {werkzeug} gingen {_taeter(ungeloest)} vor."
    if distanz_vorhanden:
        return f"Mit {werkzeug} wurde offenbar vorgegangen."
    return f"Mit {werkzeug} sollen {_taeter(ungeloest)} vorgegangen sein."


def _line_story(werkzeug_satz: str, rest_sentences: str) -> str:
    """Werkzeug-Satz + die Fakten-Saetze, die ins Story-Budget passen.

    Der Notnagel lautete bis 03.08.2026 „Die Polizei ermittelt die Hintergruende
    der {tat}." — das ergab mit einem nominativen `tat` kaputte Grammatik („der
    Versuchter Aufbruch eines Zigarettenautomaten") und wiederholte zudem das
    Thema des Schlusses. Jetzt greift er nur noch, wenn WEDER Werkzeug NOCH ein
    Fakten-Satz da ist, und nennt kein Genitiv-Objekt mehr.
    """
    teile = [t for t in (werkzeug_satz.strip(), (rest_sentences or "").strip()) if t]
    return " ".join(teile) if teile else "Die Polizei ermittelt die Hintergründe."


def _eur(n: int) -> str:
    """Eurobetrag mit deutschem Tausenderpunkt (40000 -> „40.000")."""
    return f"{n:,}".replace(",", ".")


def _line_zahlen(beute: Optional[int], schaden: Optional[int]) -> str:
    """Beute/Schaden-Satz.

    WICHTIG: 0 ist eine AUSSAGE („keine Beute"), kein fehlender Wert — deshalb
    durchgehend `is not None` statt Truthiness. Sonst entsteht der Unsinnssatz
    „Die Beute wird auf rund 0 Euro geschätzt." (real aufgetreten bei einer
    Sprengung, bei der die Täter nicht an die Kassetten kamen).
    """
    kein_schaden = "Nennenswerter Sachschaden entstand nicht."
    keine_beute = "Beute wurde keine gemacht."

    if beute is not None and schaden is not None:
        b = keine_beute if beute == 0 else f"Die Beute: rund {_eur(beute)} Euro."
        s = kein_schaden if schaden == 0 else f"Der Schaden: etwa {_eur(schaden)} Euro."
        return f"{b} {s}"
    if schaden is not None:
        return (kein_schaden if schaden == 0
                else f"Der Sachschaden liegt bei etwa {_eur(schaden)} Euro.")
    if beute is not None:
        return (f"{keine_beute} Die genaue Schadenshöhe ist noch unklar." if beute == 0
                else f"Die Beute wird auf rund {_eur(beute)} Euro geschätzt.")
    return "Die genaue Schadenshöhe ist noch unklar."


# Distanz-Pruefung liegt in core.parse (dort wohnen die reinen Text-Regeln) —
# core.lektor braucht dieselbe Pruefung fuer die Nachkontrolle seiner Vorschlaege.
_distanz_fehlt = parse.distanz_fehlt


def _line_cliffhanger(ungeloest: bool, fahndung: str = "") -> str:
    """Schluss: erst der Fahndungsstand, dann die Spur.

    `fahndung` kommt aus `parse.trenne_fahndung()` und stand bis zum 03.08.2026
    mitten in der Story. Hier gehoert er hin — „Die Fahndung verlief erfolglos"
    und „von den Taetern fehlt jede Spur" sind dieselbe Aussage. Der Schluss
    wird dadurch von selbst laenger, die Story kuerzer.
    """
    schluss = ("Von den unbekannten Tätern fehlt bis heute jede Spur — die Polizei bittet um Hinweise."
               if ungeloest else "Die Ermittlungen laufen — der Fall ist noch nicht abgeschlossen.")
    f = (fahndung or "").strip()
    return f"{f.rstrip('.')}. {schluss}" if f else schluss


def _caption(role: str, zeit: Optional[str], ungeloest: bool, tat: str) -> str:
    if role == "hook":
        return f"{zeit} Uhr" if zeit else "Mitten in der Nacht"
    if role == "eskalation":
        return "Großeinsatz"
    if role == "story":
        return (tat or "Tatgeschehen")[:40]
    if role == "zahlen":
        return "Beute vs. Schaden"
    if role == "cliffhanger":
        return "Spur: keine" if ungeloest else "Ermittlungen laufen"
    return ""


# ---------------------------------------------------------------------------
# SPEC ZUSAMMENBAUEN — PORTIERT aus assemble_spec(), gespeist mit echten Fakten
# ---------------------------------------------------------------------------
def build_spec(case: dict[str, Any], facts: dict[str, Any]) -> dict[str, Any]:
    facts = facts or {}
    ort = (facts.get("ort") or case.get("region") or "unbekannter Ort").strip()
    tat = (facts.get("tat") or case.get("title") or "Vorfall").strip()
    zeit = facts.get("zeit")
    beute = facts.get("beute_eur")
    schaden = facts.get("schaden_eur")
    ungeloest = bool(facts.get("ungeloest"))

    # ZWEITES GATE gegen Nachahmungs-Anleitungen. core.extract.sanitize() saeubert
    # schon bei der Extraktion — hier nochmal, direkt vor dem Bau des gesprochenen
    # Textes. So sind auch Bestandsfaelle abgedeckt, deren Fakten vor dieser Regel
    # entstanden sind (kein erneuter Claude-Lauf noetig).
    werkzeug = parse.entschaerfe_methode(str(facts.get("werkzeug") or "")) or None
    details = parse.entschaerfe_methode((facts.get("details") or "").strip())

    # Fahndungssatz aus dem Tathergang loesen — er traegt jetzt den Schluss.
    hergang, fahndung = parse.trenne_fahndung(details)
    saetze = _split_sentences(hergang)

    # Steht in `details` schon Konjunktiv/„mutmaßlich"? Dann braucht der
    # Werkzeug-Satz seine eigene Distanzierung nicht zu wiederholen.
    distanz_in_details = not _distanz_fehlt(details)

    # DETAILS AUF DIE ABSCHNITTE VERTEILEN — bewusst an EINER Stelle, damit
    # nachvollziehbar bleibt, welcher Satz wo landet, und jeder Abschnitt sein
    # Zeichen-Budget kennt (siehe BUDGET_SEK).
    #
    # Bis 03.08.2026: hook bekam gar keinen Satz (nur Ort/Zeit als Etikett),
    # eskalation den ersten, story ALLE uebrigen. Ergebnis am Fall Glinde:
    # hook 4,6 s, story 18,5 s.
    #
    # Der Hook nimmt den ersten Satz nur, wenn er nicht ausufert — sonst traegt
    # der gebaute Kurz-Einstieg und der Satz bleibt fuer die eskalation liegen.
    # Ohne diese Bremse lief der Hook bei Gorxheimertal auf 11,6 s.
    hook_satz = ""
    if saetze and len(saetze[0]) <= _budget("hook") * 1.3:
        hook_satz, saetze = saetze[0], saetze[1:]

    eskalations_satz, saetze = _fuellen(saetze, _budget("eskalation"))

    # Der Werkzeug-Satz gehoert zur Story und zaehlt gegen ihr Budget.
    werkzeug_satz = _werkzeug_satz(werkzeug, ungeloest, distanz_in_details)
    story_saetze, saetze = _fuellen(saetze, max(0, _budget("story") - len(werkzeug_satz)))
    # Was danach uebrig bleibt, faellt weg. Straffen ist erlaubt — dieselbe
    # Regel, nach der auch der Lektor arbeitet („Nebensaechliches darf ganz
    # wegfallen"). Die Kernfakten stecken in Ort, Zeit, Tat, Beute und Schaden
    # und werden separat gesetzt, nicht aus `details` gezogen.

    lines = {
        "hook": _line_hook(ort, zeit, tat, hook_satz, schaden),
        "eskalation": _line_eskalation(tat, eskalations_satz),
        "story": _line_story(werkzeug_satz, story_saetze),
        "zahlen": _line_zahlen(beute, schaden),
        "cliffhanger": _line_cliffhanger(ungeloest, fahndung),
    }

    # WELCHE ABSCHNITTE DIESER FALL HAT — die Form richtet sich nach dem, was
    # bekannt ist, statt jedem Fall dieselben fuenf aufzuzwingen.
    # Ohne Beute UND ohne Schaden gibt es nichts zu zeigen: bis 03.08.2026 stand
    # dort trotzdem die Bauchbinde „Beute vs. Schaden" ueber einer leeren Tafel,
    # waehrend der Sprecher „Die genaue Schadenshoehe ist noch unklar" sagte —
    # vier Sekunden fuer eine Nicht-Aussage.
    rollen = tuple(r for r in SCENE_ORDER
                   if r != "zahlen" or beute is not None or schaden is not None)

    # GUARDRAIL Unschuldsvermutung — greift NUR, wenn jemand identifiziert ist.
    # Bei unbekannten/fluechtigen Taetern (ungeloest=True) gibt es keine Person,
    # die vorverurteilt werden koennte; dort ist der Indikativ korrekt und wird
    # von Polizei und Presse selbst verwendet ("Unbekannte sprengten den
    # Automaten und fluechteten"). Ein Distanz-Zusatz waere dort vorsichtiger
    # als die Quelle — und damit unnoetig.
    # Bewusst JE ZEILE geprueft, nicht ueber alle zusammen: Sonst haette ein
    # „sollen" in der Werkzeug-Zeile eine Schuldbehauptung in der Eskalations-
    # Zeile verdeckt („Der Festgenommene sprengte den Automaten.").
    #
    # SEIT 03.08.2026 UEBER ALLE ABSCHNITTE, nicht mehr nur ueber eskalation und
    # story: Die Fakten-Saetze wandern jetzt zwischen den Abschnitten (der erste
    # traegt den Hook, der Fahndungssatz den Schluss). Damit kann eine
    # Schuldbehauptung an Stellen landen, die frueher nie geprueft wurden —
    # genau dort waere sie unbemerkt durchgerutscht.
    if not ungeloest:
        zusatz = (f"Nach bisherigen Erkenntnissen sollen {_taeter(ungeloest)} "
                  f"für die Tat verantwortlich sein.")
        for rolle in rollen:
            if _distanz_fehlt(lines[rolle]):
                lines[rolle] = f"{zusatz} {lines[rolle]}".strip()
                break   # einmal reicht — der Hinweis gilt fuer den ganzen Block

    # Deterministischer B-Roll-Seed (Titel + Quelle, damit derselbe Fall stabil bleibt)
    seed_src = f"{case.get('title', '')}|{facts.get('quelle_link') or case.get('link', '')}"
    seed = int(hashlib.md5(seed_src.encode("utf-8")).hexdigest(), 16) % 997

    # Bildplan je Abschnitt: Sorte aus dem Inhalt, Anzahl aus der geschaetzten
    # Sprechdauer. Beides haengt am Text und wird deshalb hier bestimmt.
    plan = [(r, _bild_kategorie(r, lines[r]), _bildanzahl(r, _sekunden(lines[r])))
            for r in rollen]
    zuteilung = broll_zuteilung(seed, plan)

    scenes: list[dict[str, Any]] = []
    t = 0
    for role in rollen:
        d = SCENE_DURATIONS[role]
        # Nur noch Fortschrittsbalken + Beute/Schaden-Tafel. Timer, Karte,
        # Warnbalken und Tatzeit-Label sind raus (Nutzer-Entscheid
        # 01.08.2026, siehe core/render.py) — render ignoriert die alten
        # Tags in Bestands-Specs einfach.
        overlay = ["progress"]
        if role == "zahlen":
            overlay.append("daten:beute_schaden")

        scenes.append({
            "t_start": t, "t_end": t + d, "role": role,
            "vo": lines[role],
            "caption": _caption(role, zeit, ungeloest, tat),
            "broll": zuteilung[role],
            "overlay": overlay,
            "sfx": SCENE_SFX[role],
        })
        t += d

    voiceover = " ".join(lines[r] for r in rollen)

    hashtags = ["#truecrime", "#deutschland", "#blaulicht", "#krimi", "#polizei", "#nachrichten"]
    tat_tag = re.sub(r"[^a-z0-9]+", "", tat.lower())[:20]
    if tat_tag:
        hashtags.append(f"#{tat_tag}")

    title_options = [
        f"{tat} in {ort}" + (f" — {zeit} Uhr" if zeit else ""),
        f"{ort}: {tat}" + (" — Täter flüchtig" if ungeloest else ""),
        f"So lief die {tat} in {ort}",
    ]

    return {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "channel": CHANNEL,
        "duration": t,
        "case": {
            "id": case.get("id"),
            "title": case.get("title", ""),
            "region": case.get("region", ""),
            "score": case.get("score", 0),
            "link": case.get("link", ""),
        },
        "facts": facts,
        "meta": {
            "hook_line": lines["hook"],
            "title_options": title_options,
            "caption": f"{ort}: {tat}. Was ist da los? 👇\n\n{DISCLAIMER}",
            "disclaimer": DISCLAIMER,
            "hashtags": hashtags,
        },
        "voiceover": voiceover,
        "scenes": scenes,
        "mode": "facts",
    }
