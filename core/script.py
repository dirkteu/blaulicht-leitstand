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
from typing import Any, NamedTuple, Optional

from . import parse

CHANNEL = "Nachtknall"
# GELOESCHT (04.08.2026): DURATION = 42. Die Ziel-Laenge gibt es nicht mehr —
# die Cliplaenge ergibt sich aus dem gesprochenen Text (siehe BLOECKE und
# BUDGET_SEK). Der Kommentar verwies ohnehin auf ein „durs unten", das schon
# vorher verschwunden war.

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
#
# NUR MOTIVE, DIE NICHTS BEHAUPTEN KOENNEN (Nutzer-Entscheid 04.08.2026).
#
# c3 heisst „die Taeter: Ankunft, Bewegung, Flucht". Sobald ein Motiv ein
# FAHRZEUG zeigt, behauptet das Bild ein Fluchtmittel — und die Meldung nennt
# oft ein anderes. Belegt an Glinde: dort fluechten die Taeter laut Meldung
# „auf Fahrraedern", waehrend der Topf ein wegfahrendes Auto und einen Roller
# anbot. Dieselbe Fehlerklasse wie Zigarettenautomat statt Geldautomat, nur
# weniger auffaellig.
#
# Uebrig bleiben die beiden Motive OHNE Fahrzeug — Menschen zu Fuss. Die
# koennen zu keiner Meldung im Widerspruch stehen.
#
# Draussen und warum:
#   _02 Taeter-Vorfahrt   — ankommendes Auto, behauptet ein Fahrzeug
#   _05 Flucht-Roller     — behauptet einen Roller
#   _06 Fluchtwagen       — behauptet ein Auto
#   _07 leere Strasse     — weder Taeter noch Flucht; zudem Schnee, also nur
#                           mit Winterbildern kombinierbar
# Alle bleiben im Bucket, nur in keinem Topf.
#
# PREIS DIESER ENTSCHEIDUNG: c3 hat damit nur noch ZWEI Motive. Bis der Topf
# waechst, sehen alle Videos an dieser Stelle sehr aehnlich aus.
TAETER_MOTIVE = [
    "broll_cctv_03.mp4",   # einzelne Gestalt rennt
    "broll_cctv_04.mp4",   # zwei Gestalten mit Beutetasche an der Hauswand
]

# Die uebrigen Kategorien stehen weiter auf 1 — dort liegt je ein Clip.
# `weather` gestrichen per BROLL_PLAN Beschluss 1 (umgesetzt 01.08.2026).
ASSETS = {
    "street":    [f"broll_strasse_{i:02d}.mp4"   for i in range(1, 2)],
    "blaulicht": [f"broll_blaulicht_{i:02d}.mp4" for i in range(1, 2)],
    "cctv":      list(TAETER_MOTIVE),
    "location":  [f"broll_kulisse_{i:02d}.mp4"   for i in range(1, 2)],
    "effect":    [clip for satz in EFFEKT_SAETZE for clip in satz],
}

# ---------------------------------------------------------------------------
# DER GRUNDAUFBAU — vier Bloecke, EINE Tabelle
# ---------------------------------------------------------------------------
# Bis 03.08.2026 liefen zwei Strukturen nebeneinander, die nicht zueinander
# passten: fuenf Textrollen (hook/eskalation/story/zahlen/cliffhanger) und vier
# Bildteile (die „Vier-Teile-Klammer"). Die Naht war sichtbar — der
# Zahlen-Abschnitt hing an den Taeter-Bildern, obwohl er ueber Beute und
# Schaden spricht.
#
# Jetzt gilt: ein Block = ein Gedanke = eine Bildsorte. Die REIHENFOLGE STEHT
# FEST, und der Text wird auf die Bloecke verteilt — nicht umgekehrt. Genau das
# macht einen Grundaufbau aus: der Zuschauer erkennt die Form wieder.
#
# Der Clip beginnt bewusst am ENDE der Geschichte — die Polizei kommt zuletzt,
# c2 springt zurueck zur Tat. Das ist der uebliche True-Crime-Einstieg; die
# Sprache muss den Sprung tragen, sonst wirkt er wie ein Fehler.
#
# `darf_fehlen`: Sagt eine Meldung nichts ueber die Taeter, gibt es kein c3.
# Es wird kein Text erfunden, um eine Form zu fuellen.
class Block(NamedTuple):
    id: str            # c1 … c4, zugleich `role` in der Spec
    erzaehlt: str      # was dieser Block sagt (Dokumentation)
    bild: Optional[str]   # gewuenschte Bildsorte; None = kein Bild (Farbflaeche)
    darf_fehlen: bool
    sfx: str


BLOECKE: tuple[Block, ...] = (
    Block("c1", "Einstieg: staerkster Fakt, dann Ort und Zeit", "polizei",   False, "boom"),
    Block("c2", "Die Tat",                                      "tatobjekt", True,  "sirene"),
    Block("c3", "Die Taeter: Ankunft, Bewegung, Flucht",         "taeter",    True,  "herzschlag"),
    # c4 traegt die Bilanz und braucht KEIN Material — damit ist es der einzige
    # Block, in dem nie ein falsches Bild stehen kann. `_build_background()`
    # faellt ohne Clip auf eine Farbflaeche zurueck; der gesuchte Zustand
    # existiert also bereits.
    Block("c4", "Bilanz: Zahlen, Fahndungsstand, Spur",          None,        False, "stille"),
)

# UEBERGANG bis Stufe 2: Bildsorte -> heutiger Pool. Verschwindet, sobald die
# Szene ihre Bildanforderung stellt statt eines Dateinamens.
_SORTE_POOL = {"polizei": "blaulicht", "tatobjekt": "effect", "taeter": "cctv"}

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


def _sekunden(text: str) -> float:
    """Grobe Sprechdauer eines Textes. Die echte misst spaeter `tts.synth()`;
    hier reicht die Schaetzung, weil nur die Bildanzahl daran haengt."""
    return len(text or "") / ZEICHEN_PRO_SEKUNDE + 0.35   # + Atempause, s. tts.GAP


def _bildanzahl(sekunden: float) -> int:
    """Wie viele verschiedene Bilder ein Block zeigt."""
    return min(MAX_BILDER, max(1, round(sekunden / SEK_PRO_BILD)))


# WELCHER SATZ IN WELCHEN BLOCK — die Sortierung passiert im TEXT.
#
# Kurz existierte die umgekehrte Loesung: Die Bloecke lagen fest und das BILD
# richtete sich nach dem Satz. Das war ein Zwischenschritt. Jetzt liegt die
# Bildsorte am Block fest (siehe BLOECKE) und die SAETZE werden einsortiert —
# das ist die Reihenfolge, die ein Grundaufbau braucht.
#
# Vorgeschichte, damit niemand zurueckbaut: Vorher hing die Bildsorte am
# Rollennamen. Als die Saetze einen Abschnitt nach vorn rutschten, kippte die
# Zuordnung ins GEGENTEIL — am Fall Glinde lief „…auf Fahrraedern die Flucht
# ergriffen" ueber Bildern des zerstoerten Automaten, waehrend „Der Geldautomat
# wurde vollstaendig zerstoert" Fluchtwagen und Flucht-Roller zeigte.
#
# Die Muster stehen hier und nicht in core.parse: dort wohnen nur die Regeln,
# die sich core.lektor mit uns teilt.
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


def _sortiere_saetze(saetze: list[str]) -> tuple[list[str], list[str]]:
    """Fakten-Saetze auf c2 (die Tat) und c3 (die Taeter) verteilen.

    Rueckgabe: (Saetze fuer c2, Saetze fuer c3). Bei Gleichstand entscheidet
    c2 — die Tat ist der Kern der Meldung, die Taeter sind die Ergaenzung.
    """
    tat: list[str] = []
    taeter: list[str] = []
    for s in saetze:
        if len(_FLUCHT_RE.findall(s)) > len(_OBJEKT_RE.findall(s)):
            taeter.append(s)
        else:
            tat.append(s)
    return tat, taeter

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
BUDGET_SEK = {"c1": 8, "c2": 10, "c3": 10, "c4": 11}


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


def _line_tat(werkzeug_satz: str, saetze: str) -> str:
    """c2 — die Tat: Werkzeug-Satz plus die Fakten-Saetze ueber das Tatobjekt.

    Gibt "" zurueck, wenn nichts vorliegt. c2 `darf_fehlen`, deshalb wird hier
    NICHTS erfunden: Bis 03.08.2026 stand an dieser Stelle der Notnagel „Die
    Polizei ermittelt die Hintergruende der {tat}." — mit nominativem `tat`
    kaputte Grammatik („der Versuchter Aufbruch eines Zigarettenautomaten") und
    inhaltlich eine Dopplung zur Bilanz in c4.
    """
    teile = [t for t in (werkzeug_satz.strip(), (saetze or "").strip()) if t]
    return " ".join(teile)


def _line_taeter(saetze: str) -> str:
    """c3 — die Taeter: Ankunft, Bewegung, Flucht.

    Gibt "" zurueck, wenn die Meldung nichts ueber die Taeter hergibt. Der Block
    faellt dann weg (`darf_fehlen`), statt mit einer Leerformel gefuellt zu
    werden.
    """
    return (saetze or "").strip()


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


def _line_bilanz(beute: Optional[int], schaden: Optional[int],
                 ungeloest: bool, fahndung: str = "") -> str:
    """c4 — die Bilanz: Zahlen, Fahndungsstand, Spur.

    Loest den frueheren `zahlen`-Abschnitt aus der Mitte ab. Zahlen sind eine
    Bilanz, kein Mittelteil: Standen sie in der Mitte, unterbrachen sie die
    Erzaehlung — und danach musste sie neu anlaufen, nur um zu enden.

    `_line_zahlen()` wird NUR aufgerufen, wenn mindestens ein Wert vorliegt.
    Damit verschwindet die leere Beute/Schaden-Tafel: Bis 03.08.2026 stand die
    Bauchbinde „Beute vs. Schaden" ueber einer leeren Karte, waehrend der
    Sprecher „Die genaue Schadenshoehe ist noch unklar" sagte.

    `fahndung` kommt aus `parse.trenne_fahndung()` und stand vorher mitten in
    der Story — „Die Fahndung verlief erfolglos" und „von den Taetern fehlt
    jede Spur" sind dieselbe Aussage.
    """
    teile: list[str] = []
    if beute is not None or schaden is not None:
        teile.append(_line_zahlen(beute, schaden))
    f = (fahndung or "").strip()
    if f:
        teile.append(f.rstrip(".") + ".")
    teile.append(
        "Von den unbekannten Tätern fehlt bis heute jede Spur — die Polizei bittet um Hinweise."
        if ungeloest else "Die Ermittlungen laufen — der Fall ist noch nicht abgeschlossen.")
    return " ".join(teile)


# Schlagzeile fuer c1 — kurz, gross, und bewusst OHNE Boulevard-Duktus.
#
# Form ja, Ton nein (Nutzer-Entscheid 04.08.2026): grosse fette Schrift und
# Farbkasten wie bei einer Boulevard-Schlagzeile, aber kein Ausrufezeichen,
# keine Superlative, und Rot statt des bekannten Gelbs. CLAUDE.md §6 verlangt
# „sachlich-dokumentarisch, nie reisserisch" — und begruendet das mit der
# Plattform-Moderation, nicht mit Geschmack.
#
# QUELLE IST BEWUSST `tat` + `ort`, NICHT `case.title`: Der Titel ist die
# ungefilterte Ueberschrift der Pressemeldung. `tat` und `ort` sind durch
# `extract.sanitize()` gelaufen (Ort nur auf Stadtebene) und `tat` zusaetzlich
# durch `entschaerfe_methode()`. Die Schlagzeile ist der am besten lesbare Text
# im Clip — sie darf nicht der einzige ungeprueft sein.
SCHLAGZEILE_MAX = 52


def _schlagzeile(tat: str, ort: str) -> str:
    """Kurze Schlagzeile aus geprueften Fakten."""
    t = (tat or "").strip().rstrip(".")
    if len(t) > SCHLAGZEILE_MAX:
        # Lieber hart kuerzen als drei Zeilen Kleingedrucktes gross setzen.
        t = t[:SCHLAGZEILE_MAX].rsplit(" ", 1)[0].rstrip(" ,-")
    return f"{t} in {ort}".strip() if ort else t


def _caption(block_id: str, zeit: Optional[str], ungeloest: bool, tat: str,
             hat_zahlen: bool) -> str:
    if block_id == "c1":
        return f"{zeit} Uhr" if zeit else "Mitten in der Nacht"
    if block_id == "c2":
        return (tat or "Tatgeschehen")[:40]
    if block_id == "c3":
        return "Täter auf der Flucht" if ungeloest else "Die Tatverdächtigen"
    if block_id == "c4":
        # Nur „Beute vs. Schaden" versprechen, wenn es auch Zahlen gibt.
        if hat_zahlen:
            return "Beute vs. Schaden"
        return "Spur: keine" if ungeloest else "Ermittlungen laufen"
    return ""


# ---------------------------------------------------------------------------
# SPEC ZUSAMMENBAUEN — PORTIERT aus assemble_spec(), gespeist mit echten Fakten
# ---------------------------------------------------------------------------
def build_spec(case: dict[str, Any], facts: dict[str, Any]) -> dict[str, Any]:
    facts = facts or {}
    ort = (facts.get("ort") or case.get("region") or "unbekannter Ort").strip()
    # `tat` faellt notfalls auf `case.title` zurueck — und das ist die
    # UNGEFILTERTE Ueberschrift der Pressemeldung, die nie durch
    # `extract.sanitize()` gelaufen ist. Dort stehen Namen, Strassen und
    # Methoden-Details. `tat` landet in Bauchbinde und Schlagzeile, also im am
    # besten lesbaren Text des Clips — deshalb hier durch dieselbe Schranke.
    tat = parse.entschaerfe_methode(
        (facts.get("tat") or case.get("title") or "Vorfall").strip()) or "Vorfall"
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

    # DEN TEXT AUF DIE BLOECKE VERTEILEN — bewusst an EINER Stelle, damit
    # nachvollziehbar bleibt, welcher Satz wo landet, und jeder Block sein
    # Zeichen-Budget kennt (siehe BUDGET_SEK).
    #
    # c1 nimmt den ersten Satz nur, wenn er nicht ausufert — sonst traegt der
    # gebaute Kurz-Einstieg, und der Satz bleibt fuer c2/c3 liegen. Ohne diese
    # Bremse lief der Einstieg bei Gorxheimertal auf 11,6 s.
    c1_satz = ""
    if saetze and len(saetze[0]) <= _budget("c1") * 1.3:
        c1_satz, saetze = saetze[0], saetze[1:]

    # Die uebrigen Saetze nach Inhalt auf c2 (die Tat) und c3 (die Taeter)
    # verteilen. Die Bloecke liegen fest, die SAETZE werden einsortiert.
    tat_saetze, taeter_saetze = _sortiere_saetze(saetze)

    # Der Werkzeug-Satz gehoert zu c2 und zaehlt gegen dessen Budget.
    werkzeug_satz = _werkzeug_satz(werkzeug, ungeloest, distanz_in_details)
    c2_saetze, _ = _fuellen(tat_saetze, max(0, _budget("c2") - len(werkzeug_satz)))
    c3_saetze, _ = _fuellen(taeter_saetze, _budget("c3"))
    # Was nicht ins Budget passt, faellt weg. Straffen ist erlaubt — dieselbe
    # Regel, nach der auch der Lektor arbeitet („Nebensaechliches darf ganz
    # wegfallen"). Die Kernfakten stecken in Ort, Zeit, Tat, Beute und Schaden
    # und werden separat gesetzt, nicht aus `details` gezogen.

    hat_zahlen = beute is not None or schaden is not None
    lines = {
        "c1": _line_hook(ort, zeit, tat, c1_satz, schaden),
        "c2": _line_tat(werkzeug_satz, c2_saetze),
        "c3": _line_taeter(c3_saetze),
        "c4": _line_bilanz(beute, schaden, ungeloest, fahndung),
    }

    # WELCHE BLOECKE DIESER FALL HAT. Ein Block, der nichts zu sagen hat und
    # fehlen darf, faellt weg — es wird kein Text erfunden, um eine Form zu
    # fuellen. c1 und c4 entstehen immer aus den Fakten und fehlen nie.
    bloecke = tuple(b for b in BLOECKE if lines[b.id] or not b.darf_fehlen)

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
    # SEIT 03.08.2026 UEBER ALLE BLOECKE, nicht mehr nur ueber zwei von fuenf:
    # Die Fakten-Saetze wandern zwischen den Bloecken (der erste traegt c1, der
    # Fahndungssatz c4). Damit kann eine Schuldbehauptung an Stellen landen, die
    # frueher nie geprueft wurden — genau dort waere sie unbemerkt durchgerutscht.
    if not ungeloest:
        zusatz = (f"Nach bisherigen Erkenntnissen sollen {_taeter(ungeloest)} "
                  f"für die Tat verantwortlich sein.")
        for b in bloecke:
            if _distanz_fehlt(lines[b.id]):
                lines[b.id] = f"{zusatz} {lines[b.id]}".strip()
                break   # einmal reicht — der Hinweis gilt fuer den ganzen Clip

    # Schlagzeile fuer c1. Steht hier bei den Zeilen, weil sie derselben
    # Pruefung unterliegt wie der gesprochene Text — sie ist der am besten
    # lesbare Text im Clip.
    schlagzeile = _schlagzeile(tat, ort)

    # Deterministischer B-Roll-Seed (Titel + Quelle, damit derselbe Fall stabil bleibt)
    seed_src = f"{case.get('title', '')}|{facts.get('quelle_link') or case.get('link', '')}"
    seed = int(hashlib.md5(seed_src.encode("utf-8")).hexdigest(), 16) % 997

    # Bildplan: Sorte kommt vom Block, Anzahl aus der geschaetzten Sprechdauer.
    # c4 hat keine Bildsorte und taucht deshalb gar nicht erst auf.
    plan = [(b.id, _SORTE_POOL[b.bild], _bildanzahl(_sekunden(lines[b.id])))
            for b in bloecke if b.bild]
    zuteilung = broll_zuteilung(seed, plan)

    scenes: list[dict[str, Any]] = []
    t = 0.0
    for b in bloecke:
        # Richtwert; `tts.synth()` misst den gesprochenen Text und ueberschreibt
        # t_start/t_end und `duration`. Frueher standen hier feste Soll-Dauern,
        # die mit der echten Laenge nichts zu tun hatten.
        d = round(_sekunden(lines[b.id]), 2)

        # Nur noch Fortschrittsbalken + Beute/Schaden-Tafel. Timer, Karte,
        # Warnbalken und Tatzeit-Label sind raus (Nutzer-Entscheid 01.08.2026,
        # siehe core/render.py) — render ignoriert die alten Tags in
        # Bestands-Specs einfach.
        overlay = ["progress"]
        if b.id == "c4" and hat_zahlen:
            overlay.append("daten:beute_schaden")

        szene: dict[str, Any] = {
            "t_start": round(t, 2), "t_end": round(t + d, 2), "role": b.id,
            "vo": lines[b.id],
            "caption": _caption(b.id, zeit, ungeloest, tat, hat_zahlen),
            "broll": zuteilung.get(b.id, []),
            "overlay": overlay,
            "sfx": b.sfx,
        }
        # Schlagzeile nur im Einstieg — die ersten Sekunden entscheiden, und
        # auf TikTok wird ohne Ton geschaut. In den uebrigen Bloecken wuerde
        # sie das Bild zudecken statt es zu tragen.
        if b.id == "c1":
            szene["headline"] = schlagzeile
        scenes.append(szene)
        t += d

    voiceover = " ".join(lines[b.id] for b in bloecke)

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
        # Aus dem letzten t_end statt aus der aufsummierten Gleitkommazahl —
        # sonst laufen beide um Bruchteile auseinander. `tts.synth()`
        # ueberschreibt den Wert ohnehin mit der gemessenen Laenge.
        "duration": scenes[-1]["t_end"] if scenes else 0.0,
        "case": {
            "id": case.get("id"),
            "title": case.get("title", ""),
            "region": case.get("region", ""),
            "score": case.get("score", 0),
            "link": case.get("link", ""),
        },
        "facts": facts,
        "meta": {
            "hook_line": lines["c1"],
            "title_options": title_options,
            "caption": f"{ort}: {tat}. Was ist da los? 👇\n\n{DISCLAIMER}",
            "disclaimer": DISCLAIMER,
            "hashtags": hashtags,
        },
        "voiceover": voiceover,
        "scenes": scenes,
        "mode": "facts",
    }
