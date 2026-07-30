# B-Roll 2.0 — Master-Ketten-Plan (beschlossen 2026-07-26, /grill-me)

Gemeinsames Verständnis aus der Grill-Session. Gilt als Vorgabe für den Umbau von
`core/broll_prompts.py`, der `/broll`-Seite und die erste MCP-Generierungsrunde.

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

## Umsetzungs-Todos (noch nicht begonnen)
- [ ] Bestes Frame aus `Downloads\hf_20260726_195621_ed84876a….mp4` extrahieren → `assets/master/master_intakt_roh.png`
- [ ] `core/broll_prompts.py` auf die vier Prompt-Typen umbauen (wetter raus, cctv neu, kulisse/effekt → Anim-Presets, Schutzformel als Konstante)
- [ ] `/broll`-Seite (api/main.py + Templates) an neue Prompt-Typen anpassen
- [ ] User: Higgsfield-MCP OAuth freischalten
- [ ] Runde 1 per MCP ausführen, Ergebnisse vorlegen (Stopp-Regel!)
