# -*- coding: utf-8 -*-
"""
core/broll_prompts.py  —  Higgsfield-Prompt-Baukasten (Single Source of Truth)
===============================================================================

Ziel: IMMER derselbe Automat, IMMER dieselbe Qualität. Text-zu-Video wuerfelt
sonst bei jedem Lauf Automat/Marken/Look neu. Deshalb leben die fixen
Prompt-Bloecke hier als Code-Konstanten — sie koennen nicht "aus Versehen"
umformuliert werden. Variabel sind NUR Beleuchtung/Zustand/Umfeld/Kamera-
bewegung, und zwar ausschliesslich aus den festen Auswahl-Dicts unten.

Jeder Prompt folgt dem vom Nutzer vorgegebenen Label-Format:

    [Kamera]:         fix
    [Beleuchtung]:    variabel (Auswahlliste)
    [Automat]:        fix, woertlich identisch   (bzw. [Subjekt] bei Nicht-Automat)
    [Zustand]:        variabel (Auswahlliste)
    [Umfeld]:         variabel (Auswahlliste)
    [Stil]:           fix
    [Kamerabewegung]: nur bei Video-Prompts; bei Masterbildern weglassen

Genutzt von api/main.py (Prompt-Generator auf der /broll-Seite).
"""

from __future__ import annotations

from typing import Optional


# ---------------------------------------------------------------------------
# FIXE BLOECKE — NIE UMFORMULIEREN. Konsistenz entsteht durch woertliche
# Wiederholung. Aenderungen hier aendern ALLE kuenftigen Prompts.
# ---------------------------------------------------------------------------
KAMERA_FIX = "Documentary still, shot on 35mm lens, handheld eyewitness perspective."

STIL_BASIS = (
    "Gritty photojournalistic aesthetic, cold and tense atmosphere, 4k resolution. "
    "Authentic Germany. No text watermarks, no readable license plates, "
    "no recognizable faces."
)

# Textregel fuer GENERIERTE Bilder. Dort ist erfundene Fantasieschrift das Risiko.
TEXT_REGEL_GENERIERT = (
    " STRICT TEXT RULE: the ONLY readable words allowed "
    "anywhere in the image are \"ACHTUNG\", \"ab 18\" and \"POLIZEI\". Every other "
    "sticker, label, sign, logo or lettering must be tiny, generic and blurred "
    "beyond legibility — absolutely no invented words, no gibberish lettering."
)

# Textregel fuer BEARBEITETE ECHTFOTOS. Hier kehrt sich die obige Regel um und
# richtet Schaden an — belegt am 31.07.2026 am Wandautomaten mit Absperrband:
# Das Modell hielt die echte Aufschrift "POLIZEIABSPERRUNG" fuer verboten und
# schrieb sie auf die erlaubte Wortliste um; heraus kam "ACHTUNG · ab 18 ·
# POLIZEI" auf einem Polizei-Absperrband. Dieselbe Regel leerte eine
# beschriftete Werbetafel und duennte das Streugut aus, obwohl der Vordergrund
# im Prompt dreimal als unantastbar bezeichnet war.
# Echte Schrift auf einem echten Foto ist keine Halluzination, sondern Beleg.
TEXT_REGEL_ECHTFOTO = (
    " TEXT RULE: this is a photograph of a real scene. Leave every existing "
    "word, sticker, label and piece of lettering exactly as it is, unchanged and "
    "unmoved. Do not rewrite, replace, blur or remove any text that is already "
    "in the image, and do not invent new text."
)

# Unveraendert fuer alle bestehenden Aufrufer (Platten, Kategorien, Master).
STIL_FIX = STIL_BASIS + TEXT_REGEL_GENERIERT

# Der EINE Automat (nach den Original-Fotos des Nutzers): weiss-graues
# Gehaeuse, dunkelblaue Front mit gruen-weissen Swoosh-Linien, Tasten-Spalte
# mit Marken-Miniaturen, "ab 18", ACHTUNG-Ausgabefach, rote LED-Leiste.
AUTOMAT_FIX = (
    "A real authentic German cigarette vending machine (Zigarettenautomat): a "
    "SMALL, COMPACT wall-mounted metal box, about 80 cm tall and 90 cm wide, "
    "mounted at chest height roughly 1 meter above the ground — it NEVER touches "
    "the ground and is NEVER a tall floor-standing vending machine (much smaller "
    "than a person). Off-white / light-grey steel housing; deep-blue front panel "
    "with abstract flowing green-and-white swoosh line graphics; on the right "
    "side a vertical column of small square selection buttons, each showing a "
    "tiny colored cigarette pack thumbnail (recognizable only by pack colors — "
    "red-white, gold, blue — with NO readable brand names); coin slot and "
    "banknote/EC-card reader; "
    "\"ab 18\" sticker and payment symbols at the top; horizontal delivery output "
    "tray at the bottom with a red \"ACHTUNG\" warning label; thin red vertical "
    "LED strip on the left edge. Absolutely NO glass snack front, NO shelves. "
    "Always this exact machine."
)

# ---------------------------------------------------------------------------
# PIXEL-WEG (seit 31.07.2026) — Bausteine fuer die Kette
# echtes Foto -> Freisteller -> leere Platte -> Komposit -> Bild-zu-Video.
# Konsistenz kommt hier aus PIXELN, nicht aus Text: der Automat wird nie
# generiert, sondern als freigestelltes Foto ins Bild gesetzt. Deshalb darf
# AUTOMAT_FIX in einem Platten-Prompt NIE vorkommen.
# ---------------------------------------------------------------------------

# Raeumt die Platte leer. Ohne diese Klausel stellt das Modell irgendetwas hin,
# und beim Compositing steht das Wrack dann in einer moeblierten Szene.
LEER_FIX = (
    "EMPTY SCENE, background plate: the lower two thirds of the frame are "
    "completely clear ground. Absolutely nothing lying on the ground: no "
    "objects, no debris, no machine, no vending machine, no boxes, no people, "
    "no vehicles, no bicycles."
)

# ---------------------------------------------------------------------------
# UMFAERB-WEG (seit 31.07.2026) — der GUENSTIGERE und GENAUERE Weg.
#
# Statt freizustellen und in eine generierte Platte zu setzen, wird das echte
# Tagfoto per Bild-Edit auf Nacht umgefaerbt und dabei nur der Hintergrund
# ersetzt. Die Perspektive kann nicht kippen, weil sie nie verlassen wird.
# Kostenvergleich am belegten Durchlauf: Bildvorbereitung 12 Credits gegenueber
# 90 fuer zwei Clips — der Bildteil ist ein Viertel EINES Clips.
#
# Der Komposit-Weg bleibt richtig, wenn das Objekt an einen ANDEREN Ort soll.
# ---------------------------------------------------------------------------

VORDERGRUND_TABU = (
    "the wrecked machine, its housing, the fallen front panel, every internal "
    "part, the ground it lies on, the kerb and every single piece of debris "
    "scattered around it. Identical position, identical shape, identical "
    "damage, identical perspective and camera angle. Do not move, add, remove "
    "or redesign anything in the lower half of the image."
)

HINTERGRUND_ERSATZ = (
    "remove every building, fence, house number, sign and street furniture "
    "behind the scene. In their place put a dense dark wall of unlit shrubs and "
    "overgrown trees, so that no landmark of any kind remains recognisable. "
    "The location must not be identifiable."
)

# Woertlich in JEDEN Anim-Prompt (Bild-zu-Video). Haelt Objekt und Szene fest.
SCHUTZFORMEL = (
    "Keep the machine, its position and the entire scene exactly as in the "
    "image. Do not add, remove or change any object. No people, no vehicles, "
    "no cuts."
)

# Diese Woerter loesen den Moderationsfilter aus — AUCH VERNEINT. Ein Prompt
# mit "no fire, no flames, no sparks" wurde als `nsfw` abgelehnt (31.07.2026,
# identisches Bildmaterial lief ohne die Woerter durch). Der Filter wertet
# Wortlisten ohne Verneinung. Statt "kein Feuer" also gar nichts sagen.
ANIM_VERBOTEN = (
    "fire", "flame", "flames", "spark", "sparks", "explosion", "explode",
    "blast", "detonate", "burning",
)


# ---------------------------------------------------------------------------
# FESTE AUSWAHLLISTEN — Variablen duerfen NUR hieraus kommen.
# Format: schluessel -> (deutsches UI-Label, fertiger englischer Satz)
# ---------------------------------------------------------------------------
BELEUCHTUNG: dict[str, tuple[str, str]] = {
    "nacht_laterne": (
        "Nacht — Straßenlaterne",
        "Harsh overhead sodium street lamp lighting at night, wet asphalt, "
        "high contrast, deep shadows.",
    ),
    "blaulicht": (
        "Nacht — Blaulicht",
        "Harsh overhead street lamp lighting, flickering blue emergency light "
        "reflections on wet asphalt, high contrast, deep shadows.",
    ),
    "blue_hour": (
        "Blaue Stunde (sauber)",
        "Soft even blue-hour dusk lighting, subtle reflections on clean metal, "
        "calm and clear.",
    ),
    "cctv": (
        "CCTV / Überwachung",
        "Grainy surveillance-camera look, low light, heavy sensor noise, "
        "security-camera timestamp aesthetic.",
    ),
}

ZUSTAND: dict[str, tuple[str, str]] = {
    "neu": (
        "Neu / makellos",
        "Brand-new, pristine and spotless, glossy undamaged housing, colors "
        "vivid and fresh, in perfect condition.",
    ),
    "intakt_nacht": (
        "Intakt (nachts, unheilvoll)",
        "Intact and undamaged, standing quiet and ominous in the dark.",
    ),
    "gesprengt": (
        "Gesprengt",
        "The immediate aftermath of an explosive burglary: the front panel blown "
        "wide open, heavy metal housing severely bent and buckled, door hanging "
        "on broken hinges, exposed internal product spirals and wiring, thousands "
        "of scattered cigarette packs on the ground, thin smoke drifting.",
    ),
}

UMFELD: dict[str, tuple[str, str]] = {
    "wand": (
        "An der Hauswand",
        "Mounted on the brick wall of a typical German house on a quiet "
        "residential street.",
    ),
    "pfosten": (
        "Freistehend am Pfosten",
        "Free-standing, mounted on one single galvanized steel post at the edge "
        "of a sidewalk with a green strip.",
    ),
    "isoliert": (
        "Isoliert (nur der Automat)",
        "Only the machine, centered, full machine visible, mounted on a plain "
        "neutral dark wall about 1 meter above the ground (clearly floating "
        "above the floor, never standing on it), nothing else in the frame.",
    ),
}

# BLICKWINKEL — kein Fixblock, sondern PFLICHT-PARAMETER je Objektfoto.
#
# Warum das keine Konstante sein darf: Ein Freisteller ist ein 2D-Ausschnitt mit
# EINGEBACKENEM Blickwinkel. Er laesst sich nicht drehen und nicht kippen. Also
# muss sich die Platte nach dem Foto richten — nie umgekehrt. Wurde am
# 31.07.2026 teuer gelernt: eine feste 45-Grad-Konstante, geschrieben nach dem
# ersten Wrackfoto, auf ein zweites Foto mit 25-30 Grad angewendet. Ergebnis
# unbrauchbar, egal wie sauber Freisteller und Lichtangleichung waren.
#
# Den Wert am Objektfoto ablesen: Sieht man viel von den OBERSEITEN der Objekte,
# ist die Kamera hoch (steil). Sieht man ueberwiegend die Vorderseiten, ist sie
# auf Augenhoehe (flach).
BLICKWINKEL: dict[str, tuple[str, str]] = {
    "steil": (
        "Steil von oben (~45°, Oberseiten gut sichtbar)",
        "Elevated high-angle viewpoint looking steeply down at the ground from "
        "about 2.5 meters above, roughly 45 degrees.",
    ),
    "leicht": (
        "Leicht erhöht (~25–30°, Augenhöhe im Stehen)",
        "Slightly elevated viewpoint at standing eye height, about 1.6 meters "
        "above the ground, looking down at roughly 25 degrees.",
    ),
    "flach": (
        "Flach (~10°, fast auf Bodenhöhe)",
        "Low viewpoint close to the ground, camera about 0.8 meters high, "
        "looking almost horizontally across the ground.",
    ),
}

# ORT — Umgebung der LEEREN Platte. Nicht mit UMFELD verwechseln: UMFELD sagt,
# wie der Automat montiert ist, und setzt ihn damit voraus. ORT beschreibt nur
# Boden und Hintergrund, in die spaeter etwas hineinkomponiert wird.
ORT: dict[str, tuple[str, str]] = {
    "bauzaun": (
        "Bauzaun am Grünstreifen",
        "A strip of dry unkempt grass verge on the left, a concrete kerb "
        "running diagonally through the middle, wet asphalt pavement filling "
        "the right side. Behind and above: a construction site fence of dark "
        "grey privacy mesh panels, dense dark trees and bushes rising behind "
        "it, one distant street lamp glowing.",
    ),
    "hauswand": (
        "An der Hauswand",
        "Cracked pavement slabs in the foreground meeting the plain rendered "
        "wall of a typical German residential building, a narrow strip of weeds "
        "at the base of the wall, downpipe and a closed roller shutter, no "
        "windows facing the camera.",
    ),
    "parkplatz": (
        "Supermarkt-Parkplatz",
        "Wet empty asphalt with faded white parking bay markings, a low "
        "concrete wheel stop, a trimmed hedge and a tall lamp post at the far "
        "edge, the dark flat facade of a retail building behind it.",
    ),
    "feldweg": (
        "Feldweg am Ortsrand",
        "A gravel track with grass growing down the middle, tall dry grass and "
        "nettles on both sides, a wooden fence post, open dark fields and a "
        "distant treeline behind, no buildings.",
    ),
    "tankstelle": (
        "Hinter der Tankstelle",
        "Oil-stained concrete apron in the foreground, a kerb and a strip of "
        "gravel, stacked crates and a closed metal roller door on a low utility "
        "building behind, the cold spill of a canopy light from off-frame left.",
    ),
}

KAMERABEWEGUNG: dict[str, tuple[str, str]] = {
    "keine": (
        "Keine (Standbild/Master)",
        "",
    ),
    "push_in": (
        "Langsame Kamerafahrt (push-in)",
        "A slow, steady push-in toward the machine.",
    ),
    "macro_zoom": (
        "Macro-Zoom (Detail)",
        "A slow, creeping macro zoom-in focusing on the machine and debris on "
        "the ground.",
    ),
    "cctv_statisch": (
        "CCTV statisch (leichtes Zittern)",
        "Static fixed CCTV frame with subtle digital jitter and an occasional "
        "frame glitch.",
    ),
    "tracking": (
        "Seitliche Fahrt (tracking)",
        "A slow lateral tracking shot past the scene.",
    ),
}

# Nicht-Automaten-Motive (blaulicht/strasse/wetter): gleiche Schablone,
# [Subjekt] ersetzt [Automat]/[Zustand]/[Umfeld]. Kennzeichen-Fix ist hier
# bewusst eingebaut (Test-Erkenntnis: lesbares Kennzeichen trotz Stil-Verbot).
SUBJEKT: dict[str, tuple[str, str]] = {
    "polizeiwagen": (
        "Polizeiwagen (Hook)",
        "A German police patrol car (silver-blue \"POLIZEI\" Streifenwagen) parked "
        "on a narrow residential street, blue emergency lights flashing, officers "
        "as dark shapes in the background, license plates blurred or not visible.",
    ),
    "absperrung": (
        "Absperrband am Tatort",
        "Red-and-white police barrier tape (\"POLIZEI ABSPERRUNG\") stretched "
        "across the foreground, blue light strobing across the facade of a "
        "typical German Altbau house behind it.",
    ),
    "fluchtwagen": (
        "Fluchtwagen (Cliffhanger)",
        "An empty German residential street seen from a low angle, a dark "
        "German-make car speeding away with red tail lights streaking into "
        "motion blur, license plates blurred or not visible, no people.",
    ),
    # cctv-Neudefinition (BROLL_PLAN Beschluss 3, umgesetzt 01.08.2026):
    # Taeter-Silhouetten im Ueberwachungs-Look, OHNE Automat. Zwei harte
    # Regeln in jedem Text: (1) NIE Gesichter — nur dunkle Silhouetten von
    # hinten oder aus Distanz, keine identifizierbaren Merkmale; (2) NIE die
    # Tat selbst — kein Werkzeug am Objekt, keine Handlung am Automaten,
    # nur Ankunft, Bewegung, Flucht (Guardrail "Kategorie ja, Rezept nein"
    # gilt auch fuer Bilder).
    "taeter_vorfahrt": (
        "Täter-Vorfahrt (cctv)",
        "A dark car pulling up on a deserted German street at night, doors "
        "opening, two hooded figures seen only as black silhouettes from "
        "behind, faces never visible, no identifiable features, license "
        "plates blurred or not visible.",
    ),
    "taeter_rennt": (
        "Täter rennt (cctv)",
        "A single hooded figure sprinting across an empty German street at "
        "night, seen from a distance as a dark silhouette in motion blur, "
        "face never visible, no identifiable features.",
    ),
    "taeter_gestalten": (
        "Täter-Gestalten (cctv)",
        "Two masked figures in dark clothing hurrying along a house wall at "
        "night carrying a heavy duffel bag, seen from behind as silhouettes "
        "only, faces never visible, no identifiable features.",
    ),
    "flucht_roller": (
        "Flucht-Roller (cctv)",
        "A small dark motor scooter speeding away down a narrow German "
        "street at night, rider as a dark silhouette from behind, red tail "
        "light streaking, license plate blurred or not visible, face never "
        "visible.",
    ),
    "leere_strasse": (
        "Leere Straße (ungelöst)",
        "A deserted German street at cold blue dawn, fresh black tire skid marks "
        "on the asphalt, a lone street light still glowing, empty and eerie "
        "unsolved-case mood.",
    ),
    "regen": (
        "Regen unter Laterne",
        "Heavy rain falling through the cone of a single sodium street lamp on "
        "an empty wet German street, moody and cinematic.",
    ),
    "nebel": (
        "Nebel über Straße",
        "Low fog rolling across an empty German street, diffuse halos around "
        "distant street lights, silhouettes of German houses, cold and ominous.",
    ),
}


# ---------------------------------------------------------------------------
# PROMPT ZUSAMMENBAUEN
# ---------------------------------------------------------------------------
def build_prompt(beleuchtung: str,
                 zustand: Optional[str] = None,
                 umfeld: Optional[str] = None,
                 kamerabewegung: Optional[str] = None,
                 subjekt: Optional[str] = None) -> str:
    """Fertigen Higgsfield-Prompt im Label-Format bauen.

    Automaten-Prompt:  build_prompt(beleuchtung, zustand, umfeld[, kamerabewegung])
    Subjekt-Prompt:    build_prompt(beleuchtung, subjekt=...[, kamerabewegung])

    Unbekannte Schluessel -> ValueError (Variablen NUR aus den Auswahllisten).
    """
    def pick(d: dict[str, tuple[str, str]], key: str, feld: str) -> str:
        if key not in d:
            raise ValueError(f"Unbekannter Wert fuer {feld}: {key!r} "
                             f"(erlaubt: {', '.join(d)})")
        return d[key][1]

    lines = [f"[Kamera]: {KAMERA_FIX}",
             f"[Beleuchtung]: {pick(BELEUCHTUNG, beleuchtung, 'Beleuchtung')}"]

    if subjekt is not None:
        lines.append(f"[Subjekt]: {pick(SUBJEKT, subjekt, 'Subjekt')}")
    else:
        if zustand is None or umfeld is None:
            raise ValueError("Automaten-Prompt braucht zustand UND umfeld "
                             "(oder subjekt=... fuer Nicht-Automaten-Motive).")
        lines.append(f"[Automat]: {AUTOMAT_FIX}")
        lines.append(f"[Zustand]: {pick(ZUSTAND, zustand, 'Zustand')}")
        lines.append(f"[Umfeld]: {pick(UMFELD, umfeld, 'Umfeld')}")

    lines.append(f"[Stil]: {STIL_FIX}")

    if kamerabewegung and kamerabewegung != "keine":
        lines.append(f"[Kamerabewegung]: {pick(KAMERABEWEGUNG, kamerabewegung, 'Kamerabewegung')}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# PIXEL-WEG — Platten- und Anim-Prompts
# ---------------------------------------------------------------------------

def build_platte_prompt(beleuchtung: str, ort: str, blickwinkel: str) -> str:
    """Prompt fuer eine LEERE Nacht-Platte bauen (Hintergrund ohne Objekt).

    Bewusst OHNE AUTOMAT_FIX: das Objekt kommt als freigestelltes Foto ins Bild
    und darf vom Modell nicht erfunden werden. Wer hier den Automaten
    mitbeschreibt, hat wieder zwei verschiedene Automaten.

    `blickwinkel` ist PFLICHT und wird am Objektfoto abgelesen, nicht geraten.
    Passt er nicht, ist die Platte unbrauchbar — der Freisteller laesst sich
    nachtraeglich nicht in eine andere Perspektive bringen.
    """
    if beleuchtung not in BELEUCHTUNG:
        raise ValueError(f"Unbekannte Beleuchtung: {beleuchtung!r} "
                         f"(erlaubt: {', '.join(BELEUCHTUNG)})")
    if ort not in ORT:
        raise ValueError(f"Unbekannter Ort: {ort!r} (erlaubt: {', '.join(ORT)})")
    if blickwinkel not in BLICKWINKEL:
        raise ValueError(f"Unbekannter Blickwinkel: {blickwinkel!r} "
                         f"(erlaubt: {', '.join(BLICKWINKEL)})")

    return "\n".join([
        f"[Kamera]: {KAMERA_FIX} {BLICKWINKEL[blickwinkel][1]}",
        f"[Beleuchtung]: {BELEUCHTUNG[beleuchtung][1]}",
        f"[Ort]: {ORT[ort][1]}",
        f"[Leer]: {LEER_FIX}",
        f"[Stil]: {STIL_FIX}",
    ])


def build_umfaerben_prompt(beleuchtung: str, hintergrund: str = HINTERGRUND_ERSATZ,
                           vordergrund: str = VORDERGRUND_TABU) -> str:
    """Prompt fuer den Umfaerb-Weg bauen (echtes Tagfoto -> Nachtszene).

    Der guenstigere und genauere Weg: statt das Objekt freizustellen und in eine
    generierte Platte zu setzen, wird das ORIGINALFOTO umgefaerbt. Die
    Perspektive kann dabei nicht kippen, weil sie nie verlassen wird — das
    Problem, an dem der Komposit-Weg am 31.07.2026 gescheitert ist.

    Dreiteilig, und die Reihenfolge ist Absicht: erst was bleiben MUSS, dann was
    weg SOLL, dann das Licht. Umgekehrt formuliert raeumt das Modell zu viel weg.

    Nutzt bewusst TEXT_REGEL_ECHTFOTO statt der STRICT TEXT RULE aus STIL_FIX —
    Begruendung samt Beleg steht bei der Konstante. Wer hier STIL_FIX einsetzt,
    bekommt umgeschriebene Absperrbaender zurueck.
    """
    if beleuchtung not in BELEUCHTUNG:
        raise ValueError(f"Unbekannte Beleuchtung: {beleuchtung!r} "
                         f"(erlaubt: {', '.join(BELEUCHTUNG)})")
    return "\n\n".join([
        "Two separate instructions, both mandatory.",
        f"FOREGROUND, keep completely untouched: {vordergrund}",
        f"BACKGROUND, replace entirely: {hintergrund}",
        f"Relight the whole scene from daylight to night-time: "
        f"{BELEUCHTUNG[beleuchtung][1]} {STIL_BASIS}{TEXT_REGEL_ECHTFOTO}",
    ])


def pruefe_anim_prompt(text: str) -> list[str]:
    """Verbotene Woerter in einem Anim-Prompt finden (leere Liste = sauber).

    Harte Pruefung statt blossem Vorsatz — Prompt-Regeln allein haben in diesem
    Projekt mehrfach versagt. Siehe ANIM_VERBOTEN fuer die Begruendung.
    """
    klein = text.lower()
    return [w for w in ANIM_VERBOTEN if w in klein]


def build_anim_prompt(bewegung: str, atmosphaere: str = "") -> str:
    """Anim-Prompt fuer Bild-zu-Video bauen (Kamerabewegung + Schutzformel).

    `bewegung` beschreibt NUR die Kamera, `atmosphaere` optional Dunst o.ae.
    Das Objekt wird mit keinem Wort beschrieben — es steht ja im Startbild.

    Verbotene Woerter loesen ValueError aus, statt eine abgelehnte Generierung
    zu riskieren.
    """
    teile = [bewegung.strip()]
    if atmosphaere.strip():
        teile.append(atmosphaere.strip())
    teile.append(SCHUTZFORMEL)
    prompt = " ".join(teile)

    gefunden = pruefe_anim_prompt(prompt)
    if gefunden:
        raise ValueError(
            f"Anim-Prompt enthaelt Filter-Woerter: {', '.join(gefunden)}. "
            "Auch verneint nicht verwenden: der Moderationsfilter wertet ohne "
            "Verneinung und lehnt die Generierung ab.")
    return prompt


# ---------------------------------------------------------------------------
# KATEGORIE-PRESETS — ein Klick je B-Roll-Kategorie (Bucket-Namensschema
# broll_<kategorie>_NN.mp4, siehe contracts.BROLL_KATEGORIEN + script.ROLE_BROLL).
# Jedes Preset = fertige Baustein-Kombination passend zur Szenen-Rolle im Clip.
# ---------------------------------------------------------------------------
KATEGORIE_PRESETS: dict[str, dict[str, Optional[str]]] = {
    "blaulicht": {
        "label": "blaulicht — Hook (Polizei am Tatort)", "rolle": "hook",
        "subjekt": "polizeiwagen", "beleuchtung": "blaulicht",
        "zustand": None, "umfeld": None, "bewegung": "push_in",
    },
    "effekt": {
        "label": "effekt — Eskalation (Automat gesprengt)", "rolle": "eskalation",
        "subjekt": None, "beleuchtung": "nacht_laterne",
        "zustand": "gesprengt", "umfeld": "wand", "bewegung": "macro_zoom",
    },
    "cctv": {
        "label": "cctv — Story (Überwachungs-Look)", "rolle": "story",
        "subjekt": None, "beleuchtung": "cctv",
        "zustand": "intakt_nacht", "umfeld": "wand", "bewegung": "cctv_statisch",
    },
    "kulisse": {
        "label": "kulisse — Zahlen (Tatort-Establishing)", "rolle": "zahlen",
        "subjekt": None, "beleuchtung": "nacht_laterne",
        "zustand": "intakt_nacht", "umfeld": "pfosten", "bewegung": "push_in",
    },
    "strasse": {
        "label": "strasse — Cliffhanger (Flucht/leer)", "rolle": "cliffhanger",
        "subjekt": "fluchtwagen", "beleuchtung": "nacht_laterne",
        "zustand": None, "umfeld": None, "bewegung": "keine",
    },
    "wetter": {
        "label": "wetter — Atmosphäre (Reserve)", "rolle": "—",
        "subjekt": "regen", "beleuchtung": "nacht_laterne",
        "zustand": None, "umfeld": None, "bewegung": "keine",
    },
}


def build_kategorie_prompt(kategorie: str) -> str:
    """Fertigen Clip-Prompt fuer eine B-Roll-Kategorie bauen (Preset-Kombination)."""
    if kategorie not in KATEGORIE_PRESETS:
        raise ValueError(f"Unbekannte Kategorie: {kategorie!r} "
                         f"(erlaubt: {', '.join(KATEGORIE_PRESETS)})")
    p = KATEGORIE_PRESETS[kategorie]
    return build_prompt(beleuchtung=p["beleuchtung"], zustand=p["zustand"],
                        umfeld=p["umfeld"], kamerabewegung=p["bewegung"],
                        subjekt=p["subjekt"])


# ---------------------------------------------------------------------------
# MASTER-PRESETS — Standbilder als Konsistenz-Anker.
# Workflow: Master EINMAL festlegen -> alle Automaten-Clips als Bild->Video
# aus dem Master ableiten (nur Kamerafahrt animieren), NICHT neu wuerfeln.
# ---------------------------------------------------------------------------
MASTER_PRESETS: dict[str, dict[str, str]] = {
    "master_automat_neu": {
        "label": "Master: Automat NEU (isoliert)",
        "beleuchtung": "blue_hour", "zustand": "neu", "umfeld": "isoliert",
    },
    "master_automat_gesprengt": {
        "label": "Master: Automat GESPRENGT (isoliert)",
        "beleuchtung": "nacht_laterne", "zustand": "gesprengt", "umfeld": "isoliert",
    },
}

WORKFLOW_HINWEIS = (
    "Master-Workflow: Masterbild EINMAL generieren und festlegen (rollen, bis es "
    "sitzt). Danach alle Automaten-Clips als Bild→Video AUS diesem Master ableiten "
    "— nur die Kamerabewegung animieren, nie den Automaten neu wuerfeln."
)


def build_master_prompt(preset: str) -> str:
    """Fertigen Master-Prompt (Standbild, ohne Kamerabewegung) aus einem Preset."""
    if preset not in MASTER_PRESETS:
        raise ValueError(f"Unbekanntes Preset: {preset!r} "
                         f"(erlaubt: {', '.join(MASTER_PRESETS)})")
    p = MASTER_PRESETS[preset]
    return build_prompt(beleuchtung=p["beleuchtung"], zustand=p["zustand"],
                        umfeld=p["umfeld"], kamerabewegung=None)
