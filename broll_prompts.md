# Blaulicht — Higgsfield B-Roll-Prompts (ARCHIV)

> ⚠️ **Veraltet — Quelle ist jetzt der Prompt-Generator im Leitstand:**
> http://localhost:8000/broll (Sektion „Prompt-Generator"). Die fixen Blöcke
> ([Kamera]/[Automat]/[Stil]) leben in `core/broll_prompts.py` und garantieren:
> immer derselbe Automat, immer dieselbe Qualität. Diese Datei bleibt nur als
> Archiv/Referenz der ersten Prompt-Generation stehen.

Nische: **Zigaretten- + Geldautomaten-Sprengung**, Deutschland, Nacht, photojournalistisch.
Jeder Block ist ein kompletter Prompt (Stil-Baustein schon eingesetzt). Dateiname = Überschrift.

**Regeln fürs Generieren**
- Als kurzen `.mp4`-Clip (~5–8 s) exportieren, Name exakt wie die Überschrift.
- Über die `/broll`-Seite in den Bucket laden.
- Willst du mehr als 4 pro Kategorie? Denselben Prompt erneut laufen lassen (Higgsfield liefert jedes Mal ein anderes Bild) und als `_05`, `_06` … speichern.
- **Guardrail:** in den CCTV-Prompts NIE erkennbare Gesichter — nur vermummte Silhouetten.

---

## 1. HOOK-Kulisse → `broll_blaulicht_NN.mp4` (Polizei/Blaulicht am Tatort)

### broll_blaulicht_01.mp4
```
A German police patrol car (silver-blue "POLIZEI" Streifenwagen) parked on a narrow residential street, blue emergency lights flashing and reflecting on wet asphalt, two officers in German police uniforms in the background as dark shapes. A photorealistic, gritty eyewitness photograph, set in Germany at night. Illuminated by a harsh overhead street lamp and a direct camera flash, casting sharp highlights and deep shadows. Raw photojournalistic style. Authentic German setting — German architecture, German-plate vehicles, German signage in German language. No text watermarks, no readable license plates, no recognizable faces.
Camera Movement: slow handheld push-in toward the flashing blue lights.
```

### broll_blaulicht_02.mp4
```
Blue police lights strobing across the brick facade of a typical German Altbau apartment house, a strip of red-and-white barrier tape ("POLIZEI ABSPERRUNG") stretched across the foreground. A photorealistic, gritty eyewitness photograph, set in Germany at night. Illuminated by a harsh overhead street lamp and a direct camera flash, casting sharp highlights and deep shadows. Raw photojournalistic style. Authentic German setting — German architecture, German-plate vehicles, German signage in German language. No text watermarks, no readable license plates, no recognizable faces.
Camera Movement: slow pan across the taped-off scene.
```

### broll_blaulicht_03.mp4
```
Extreme close-up of the rotating blue light bar on the roof of a German Streifenwagen, rain droplets on the metal, blue glow smearing into the dark night behind it. A photorealistic, gritty eyewitness photograph, set in Germany at night. Illuminated by a harsh overhead street lamp and a direct camera flash, casting sharp highlights and deep shadows. Raw photojournalistic style. Authentic German setting — German architecture, German-plate vehicles, German signage in German language. No text watermarks, no readable license plates, no recognizable faces.
Camera Movement: slow tilt across the strobing light bar.
```

### broll_blaulicht_04.mp4
```
Two German police cars blocking a narrow suburban street at an odd angle, blue lights flooding the scene, lit windows of neighboring houses, silhouettes of onlookers behind a fence. A photorealistic, gritty eyewitness photograph, set in Germany at night. Illuminated by a harsh overhead street lamp and a direct camera flash, casting sharp highlights and deep shadows. Raw photojournalistic style. Authentic German setting — German architecture, German-plate vehicles, German signage in German language. No text watermarks, no readable license plates, no recognizable faces.
Camera Movement: slow dolly forward past the parked police cars.
```

---

## 2. ESKALATION → `broll_effekt_NN.mp4` (Sprengungs-Nachwirkung — dein Hero-Motiv)

### broll_effekt_01.mp4
```
The immediate aftermath of an explosive burglary of a small compact heavy red metal cigarette vending machine mounted on a single steel post in Germany at night. The steel front door blown wide open, severely bent, hanging on broken hinges; vertical spiral product rows exposed, absolutely NO glass front and NO snack shelves; thousands of small cigarette packs scattered across the wet asphalt sidewalk and grass; thin smoke still drifting. A photorealistic, gritty eyewitness photograph, set in Germany at night. Illuminated by a harsh overhead street lamp and a direct camera flash, casting sharp highlights and deep shadows. Raw photojournalistic style. Authentic German setting. No text watermarks, no readable license plates, no recognizable faces.
Camera Movement: a slow creeping macro zoom-in on the blown-open metal box and scattered debris.
```

### broll_effekt_02.mp4
```
The aftermath of a blown-open German bank ATM inside a small bank vestibule (Sparkasse-red or Volksbank-blue branding), buckled metal panels, drifting smoke and dust, euro banknotes scattered across the floor, an alarm light glowing red on the wall. A photorealistic, gritty eyewitness photograph, set in Germany at night. Illuminated by harsh interior lighting and a direct camera flash, casting sharp highlights and deep shadows. Raw photojournalistic style. Authentic German setting. No text watermarks, no readable license plates, no recognizable faces.
Camera Movement: slow drift through the smoke toward the wrecked machine.
```

### broll_effekt_03.mp4
```
Extreme close-up of a twisted red steel door hanging off broken hinges on a destroyed cigarette vending machine, faint orange embers and smoke, individual cigarette packs lying on wet ground in the foreground. A photorealistic, gritty eyewitness photograph, set in Germany at night. Illuminated by a harsh overhead street lamp and a direct camera flash, casting sharp highlights and deep shadows. Raw photojournalistic style. Authentic German setting. No text watermarks, no readable license plates, no recognizable faces.
Camera Movement: slow macro pan across the mangled metal and debris.
```

### broll_effekt_04.mp4
```
A scorched, soot-blackened section of a German house wall where a wall-mounted cigarette vending machine has been blown apart, a field of twisted metal fragments and cigarette packs on the pavement below, faint flames flickering. A photorealistic, gritty eyewitness photograph, set in Germany at night. Illuminated by a harsh overhead street lamp and a direct camera flash, casting sharp highlights and deep shadows. Raw photojournalistic style. Authentic German setting. No text watermarks, no readable license plates, no recognizable faces.
Camera Movement: slow push-in on the scorched wall and debris field.
```

---

## 3. STORY → `broll_cctv_NN.mp4` (Überwachungs-Look — KEINE Gesichter)

### broll_cctv_01.mp4
```
Grainy black-and-white surveillance-camera footage, high angle, of two hooded figures in dark clothing with faces NOT visible, approaching a small red German cigarette vending machine on a steel post at night; heavy sensor noise, low contrast, security-camera timestamp aesthetic. A photorealistic, gritty eyewitness photograph, set in Germany at night. Raw photojournalistic surveillance style. Authentic German setting. No text watermarks, no readable license plates, no recognizable faces.
Camera Movement: static CCTV frame with subtle digital jitter.
```

### broll_cctv_02.mp4
```
Grainy green-tinted night-vision CCTV view of hooded silhouettes working quickly at a German bank ATM vestibule, faces obscured, motion blur, surveillance timestamp in the corner, occasional frame glitch. A photorealistic, gritty eyewitness photograph, set in Germany at night. Raw photojournalistic surveillance style. Authentic German setting. No text watermarks, no readable license plates, no recognizable faces.
Camera Movement: slight fixed-camera drift with a brief glitch.
```

### broll_cctv_03.mp4
```
Low-resolution color surveillance footage of a dark German-make car pulling up to a curb at night, a single hooded figure with face obscured stepping out toward a cigarette machine, heavy compression artifacts, timestamp overlay look. A photorealistic, gritty eyewitness photograph, set in Germany at night. Raw photojournalistic surveillance style. Authentic German setting. No text watermarks, no readable license plates, no recognizable faces.
Camera Movement: fixed high-angle CCTV shot, no movement.
```

### broll_cctv_04.mp4
```
Grainy monochrome CCTV of a hooded figure crouching at the base of a German cigarette vending machine then sprinting out of frame, strong motion blur, night-time infrared surveillance look, faces never visible. A photorealistic, gritty eyewitness photograph, set in Germany at night. Raw photojournalistic surveillance style. Authentic German setting. No text watermarks, no readable license plates, no recognizable faces.
Camera Movement: static camera, subject blurs across the frame.
```

---

## 4. ZAHLEN → `broll_kulisse_NN.mp4` (Tatort-Establishing, intakter Automat)

### broll_kulisse_01.mp4
```
An intact small red German cigarette vending machine mounted on a single steel post on a quiet German suburban street at night, empty and ominous, a sodium street lamp glowing overhead, parked German cars along the curb. A photorealistic, gritty eyewitness photograph, set in Germany at night. Illuminated by a harsh overhead street lamp and a direct camera flash, casting sharp highlights and deep shadows. Raw photojournalistic style. Authentic German setting. No text watermarks, no readable license plates, no recognizable faces.
Camera Movement: slow steady dolly toward the machine.
```

### broll_kulisse_02.mp4
```
The entrance of a small German bank branch at night, an illuminated "Geldautomat" sign glowing, an ATM visible through the glass door, a deserted street reflected in the glass. A photorealistic, gritty eyewitness photograph, set in Germany at night. Illuminated by the sign's glow and a direct camera flash, casting sharp highlights and deep shadows. Raw photojournalistic style. Authentic German setting. No text watermarks, no readable license plates, no recognizable faces.
Camera Movement: slow push-in toward the illuminated ATM sign.
```

### broll_kulisse_03.mp4
```
A red cigarette vending machine bolted to the brick wall of a typical German house on an empty residential street at night, sodium lamp light, long shadows, cold and still atmosphere. A photorealistic, gritty eyewitness photograph, set in Germany at night. Illuminated by a harsh overhead street lamp and a direct camera flash, casting sharp highlights and deep shadows. Raw photojournalistic style. Authentic German setting. No text watermarks, no readable license plates, no recognizable faces.
Camera Movement: slow lateral tracking shot past the machine.
```

### broll_kulisse_04.mp4
```
The interior of a small German bank ATM vestibule at night, an intact ATM screen glowing softly, deserted, cold fluorescent light, a glass door reflecting the empty street outside. A photorealistic, gritty eyewitness photograph, set in Germany at night. Illuminated by cold fluorescent light and a direct camera flash, casting sharp highlights and deep shadows. Raw photojournalistic style. Authentic German setting. No text watermarks, no readable license plates, no recognizable faces.
Camera Movement: slow push-in toward the glowing ATM screen.
```

---

## 5. CLIFFHANGER → `broll_strasse_NN.mp4` (Flucht / unaufgeklärt)

### broll_strasse_01.mp4
```
An empty German residential street at night seen from a low angle, a dark German-make car (VW or Audi) speeding away with red tail lights streaking into motion blur, wet reflective asphalt, no people. A photorealistic, gritty eyewitness photograph, set in Germany at night. Illuminated by a harsh overhead street lamp, casting sharp highlights and deep shadows. Raw photojournalistic style. Authentic German setting. No text watermarks, no readable license plates, no recognizable faces.
Camera Movement: low static shot as the car accelerates away into the dark.
```

### broll_strasse_02.mp4
```
A deserted German street at cold blue dawn, fresh black tire skid marks on the asphalt, a lone street light still glowing, empty and eerie unsolved-case mood. A photorealistic, gritty eyewitness photograph, set in Germany at pre-dawn. Casting sharp highlights and deep shadows. Raw photojournalistic style. Authentic German setting. No text watermarks, no readable license plates, no recognizable faces.
Camera Movement: slow tilt down from the street light to the skid marks.
```

### broll_strasse_03.mp4
```
A dark narrow German back alley at night, a dropped crowbar and a discarded dark glove lying on the wet cobblestones, the edge of red-and-white police barrier tape in the corner of the frame. A photorealistic, gritty eyewitness photograph, set in Germany at night. Illuminated by a harsh overhead street lamp and a direct camera flash, casting sharp highlights and deep shadows. Raw photojournalistic style. Authentic German setting. No text watermarks, no readable license plates, no recognizable faces.
Camera Movement: slow creeping push-in toward the dropped tools.
```

### broll_strasse_04.mp4
```
A long empty German country road at night, a single pair of red tail lights vanishing into the distant darkness, dense treeline on both sides, cold and lonely. A photorealistic, gritty eyewitness photograph, set in Germany at night. Illuminated only by the distant tail lights and moonlight, deep shadows. Raw photojournalistic style. Authentic German setting. No text watermarks, no readable license plates, no recognizable faces.
Camera Movement: static shot as the tail lights shrink into the dark.
```

---

## 6. (Optional) Atmosphäre → `broll_wetter_NN.mp4`

> Wird von der Standard-Rollen-Zuordnung nicht automatisch gezogen — nur nützlich, wenn wir später eine Rolle darauf legen. Kannst du zunächst weglassen.

### broll_wetter_01.mp4
```
Heavy rain falling through the cone of a single German sodium street lamp on an empty wet street at night, deep shadows, moody and cinematic. A photorealistic, gritty eyewitness photograph, set in Germany at night. Casting sharp highlights and deep shadows. Raw photojournalistic style. Authentic German setting. No text watermarks, no readable license plates, no recognizable faces.
Camera Movement: slow static shot, rain streaking past the lamp.
```

### broll_wetter_02.mp4
```
Low fog rolling across an empty German street at night, diffuse halos around distant street lights, silhouettes of German houses, cold and ominous. A photorealistic, gritty eyewitness photograph, set in Germany at night. Deep shadows, raw photojournalistic style. Authentic German setting. No text watermarks, no readable license plates, no recognizable faces.
Camera Movement: very slow forward drift into the fog.
```
