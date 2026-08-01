# B-Roll 2.0 — Master-Ketten-Plan (beschlossen 2026-07-26, /grill-me)

Gemeinsames Verständnis aus der Grill-Session. Gilt als Vorgabe für den Umbau von
`core/broll_prompts.py`, der `/broll`-Seite und die erste MCP-Generierungsrunde.

---

## ⚠️ TEILWEISE ÜBERHOLT (31.07.2026) — erst hier weiterlesen

Der **Mechanismus** dieses Plans (Konsistenz über ein Masterbild statt über Text)
hat sich bestätigt. Der **Weg zum Master** ist überholt: Er kommt jetzt aus einem
echten Foto statt aus einer Generierung. Konkret:

| Punkt | Stand |
|---|---|
| Beschluss 4, Master-Kette Schritt „Frame aus `hf_20260726_195621` extrahieren" | **überholt** — der Master entsteht aus einem echten Wrackfoto des Users |
| Beschluss 4, „gesprengt-Master per Bild-Edit ableiten" | **überholt** — kein Bild-Edit mehr nötig |
| Beschluss 4, „ACHTUNT → ACHTUNG korrigieren" | **entfällt** — ein echtes Foto hat keine Halluzinations-Schrift |
| Beschluss 5, „Variation NUR über Kamerabewegung, Beleuchtung/Ort eingefroren" | **aufgehoben** — siehe unten |
| Beschluss 7, „OAuth durch den User noch offen" | **erledigt** — der claude.ai-Connector ist autorisiert |
| Beschlüsse 1, 2, 3, 6, 8 | **gelten unverändert** |

**Warum Beschluss 5 fällt:** Das Einfrieren von Ort und Beleuchtung war nötig,
weil Textprompts den Automaten nicht stillhalten konnten — jede Ortsänderung war
ein Risiko, einen anderen Automaten zu bekommen. Er kommt jetzt als
freigestelltes Foto ins Bild und **kann** nicht mehr variieren. Ort und
Beleuchtung dürfen deshalb wieder frei wechseln. Die Vielfalt, die dieser Plan
opfern musste, ist zurück.

**Der neue Weg** — zwei Betriebsarten (Belege in BETRIEB.md, Abschnitte
„B-Roll aus echtem Bildmaterial" und „Umfärben schlägt Komposit"):

```
STANDARD — umfärben:
echtes Foto → gpt_image_2 (Nacht + Hintergrund ersetzt) → 9:16 beschneiden
            → tools/kader.py → seedance_2_0 i2v → Clip

NUR wenn das Objekt an einen ANDEREN Ort soll — komposit:
echtes Foto → tools/freistellen.py → soul_location (LEERE Platte)
            → tools/komposit.py → tools/kader.py → seedance_2_0 i2v → Clip
```

Der Umfärb-Weg ist günstiger und trifft die Perspektive zwangsläufig, weil er sie
nie verlässt. Bedient wird beides über den Slash-Command **`/broll`**.

---

## Warum
Zwei Higgsfield-Läufe mit wörtlich identischem `[Automat]`-Block lieferten zwei
verschiedene Automaten (Beweis: `hf_20260726_195621…` = kompakter Pfosten-Automat ✅,
`hf_20260726_194251…` = bodenstehender Innenraum-Automat ❌). **Text allein erzwingt
keine Konsistenz.** Konsistenz kommt ab jetzt aus einem Masterbild, nie mehr aus Text.

## Beschlüsse

1. **Fünf Kategorien:** `blaulicht`, `kulisse`, `cctv`, `effekt`, `strasse`.
   `wetter` wird ersatzlos gestrichen (Preset, Bucket-Kategorie, Doku).
2. **Nur `kulisse` (Automat intakt) und `effekt` (Automat gesprengt) zeigen den
   Automaten.** Sonst niemand.
3. **`cctv` neu definiert:** Täter-Silhouetten im Überwachungs-Look (dunkles Auto
   fährt vor, vermummte Gestalten, Figur rennt durchs Bild) — **ohne Automat**,
   nie Gesichter (Guardrail bleibt).
4. **Master-Bild-Kette (Mechanismus):**
   - Kanonischer Ort = **Pfosten-Szene aus Video `hf_20260726_195621…`**
     (bestes Frame extrahieren → `assets/master/master_intakt.png`).
   - Edit 1: „ACHTUNT" → „ACHTUNG" korrigieren.
   - **Gesprengt-Master per Bild-Edit aus dem intakten Master ableiten**
     (nie neu generieren) → `assets/master/master_gesprengt.png`.
   - Alle kulisse-/effekt-Clips = **Bild→Video aus dem jeweiligen Master**.
   - Einmal Pfosten, immer Pfosten. Derselbe Automat, für immer.
5. **Variation nur über Kamerabewegung** im Bild→Video-Schritt. Beleuchtung und
   Ort sind bei kulisse+effekt eingefroren (Auswahllisten dort raus). Mehr
   Vielfalt später ausschließlich über einen kompletten zweiten Master-Satz
   (Master B an anderem Ort), nie über Einzelclip-Würfeln.
6. **Vier Prompt-Typen** (Umbau `core/broll_prompts.py`):
   | Typ | Wann | Eingabe → Ausgabe | Kategorien |
   |---|---|---|---|
   | 1. Master-Prompt | einmalig / je Master-Satz | Text → Bild | Fundament kulisse+effekt |
   | 2. Edit-Prompt | einmalig | Masterbild + Text → Bild | ACHTUNG-Fix; intakt→gesprengt |
   | 3. Anim-Prompt | pro Clip | Masterbild + Text → Video | `kulisse`, `effekt` |
   | 4. Szenen-Prompt | pro Clip | Text → Video (wie bisher) | `blaulicht`, `cctv`, `strasse` |
   **Eiserne Regel Typ 3:** Der Anim-Prompt beschreibt den Automaten mit keinem
   Wort. Nur `[Kamerabewegung]` + `[Bewegung im Bild]` (z. B. „dünner Rauch
   zieht") + Schutzformel: *„Keep the machine, its position and the entire
   scene exactly as in the image."*
7. **Higgsfield MCP — voller Einstieg:** Generierung läuft künftig über den
   MCP-Server (`claude mcp add higgsfield https://mcp.higgsfield.ai/mcp` ist
   eingerichtet). **OAuth noch offen** — User schaltet einmalig frei
   (claude.ai-Connector-Einstellungen bzw. `/mcp` in interaktiver Session).
   Testmodell: **Seedance 2.0** (i2v-fähig). Referenz: YouTube HiGniMLoJdQ
   („YouTube-Kanal mit Fable 5 automatisiert", Higgsfield-Guide
   https://higgsfield.ai/blog/faceless-channel).
8. **Runde 1 bewusst klein (Budget-Korsett):**
   1 ACHTUNG-Edit + 2–3 gesprengt-Edit-Versuche + je **2** Anim-Clips für
   kulisse und effekt. Danach **Stopp** → User-Review → erst dann Runde 2
   (Rest-Clips auf je 4 auffüllen + neue cctv/blaulicht/strasse-Clips).
   Publish-Guardrails unberührt: nichts wird automatisch veröffentlicht.

## Umsetzungs-Todos (Stand 31.07.2026)
- [x] ~~Bestes Frame aus `hf_20260726_195621….mp4` extrahieren~~ — hinfällig, Master kommt aus echtem Foto
- [x] Schutzformel als Konstante — `broll_prompts.SCHUTZFORMEL`, dazu `LEER_FIX`, `ORT`, `ANIM_VERBOTEN`, `build_platte_prompt()`, `build_anim_prompt()`
- [x] User: Higgsfield-MCP OAuth freischalten — Connector ist autorisiert
- [x] Runde 1 für `effekt` ausgeführt: 4 Clips, davon 2 empfohlen (`effekt_01_pushin`, `effekt_03_seitwaerts` in `assets/master/`). **Stopp-Regel greift: warten auf Review.**
- [ ] Freigegebene Clips über die `/broll`-Seite in den Bucket laden
- [ ] ~~`kulisse`-Master bauen — **blockiert:** braucht Original-Fotos des *unbeschädigten* Automaten~~
      **hinfällig (01.08.2026):** Seit der Vier-Teile-Klammer (UEBERLEGUNG_DRAMATURGIE.md)
      hängt `kulisse` an keiner Szenen-Rolle mehr — blockiert nichts. Bei Bedarf später.
- [x] **Täter-/Flucht-Clips für `cctv` generiert (Beschluss 3) — erledigt 01.08.2026:**
      6 Clips (Vorfahrt, rennt, Gestalten mit Beutetasche, Roller, Fluchtwagen,
      leere Straße), Seedance 2.0 t2v, 135 Credits, alle 6 vom User freigegeben
      und als `broll_cctv_02`–`07` im Bucket. Pool in `script.ASSETS` auf
      `range(2, 8)` — der Altclip `_01` (intakter Automat) bleibt draußen wie
      `effekt_01`. Neue SUBJEKT-Einträge in `core/broll_prompts.py`.
      **Damit ist kein B-Roll-Engpass mehr offen — ab hier gilt das Ship-Gate
      (CLAUDE.md §7): veröffentlichen, nicht weiter generieren.**
- [x] `wetter` aus `core/contracts.py` streichen (Beschluss 1) — **erledigt 01.08.2026** im großen Aufräumen: dazu flogen ASSETS-Eintrag, Preset und die Subjekte regen/nebel
- [ ] `/broll`-Seite (api/main.py + Templates) um die Platten-Prompts erweitern (optional — der Slash-Command deckt den Weg bereits ab)
