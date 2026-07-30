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

STIL_FIX = (
    "Gritty photojournalistic aesthetic, cold and tense atmosphere, 4k resolution. "
    "Authentic Germany. No text watermarks, no readable license plates, "
    "no recognizable faces. STRICT TEXT RULE: the ONLY readable words allowed "
    "anywhere in the image are \"ACHTUNG\", \"ab 18\" and \"POLIZEI\". Every other "
    "sticker, label, sign, logo or lettering must be tiny, generic and blurred "
    "beyond legibility — absolutely no invented words, no gibberish lettering."
)

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
