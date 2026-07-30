# -*- coding: utf-8 -*-
"""
api/main.py — FastAPI-App für den Blaulicht-Leitstand (Team 1)
================================================================

Dashboard + Review-UI. Zustand lebt ausschließlich in Supabase
(blaulicht.cases.state, core.contracts.State) — diese App liest/schreibt
Fälle über core.supa und reiht Jobs in RQ/Redis ein. Die Fach-Logik pro
Pipeline-Stufe (ingest/extract/script/tts/render/publish) gehört den
jeweiligen Workern (Team 2–5); die api ruft sie nur per Queue-Name auf.

Benötigte Pakete: ausschließlich aus requirements.txt (fastapi, uvicorn,
jinja2, python-multipart, rq, redis, supabase). KEIN zusätzliches Paket
nötig — die MVP-Session-Auth ist bewusst mit einem selbstgebauten
HMAC-signierten Cookie umgesetzt (nur stdlib: hmac/hashlib/base64), damit
NICHT extra `itsdangerous` (für Starlettes SessionMiddleware) in
requirements.txt ergänzt werden musste. Später: Supabase Auth (siehe
Abschnitt "AUTH" unten).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import tempfile
import time
from collections import Counter
from datetime import datetime
from typing import Any, Optional

from fastapi import FastAPI, Form, Query, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from redis import Redis
from rq import Queue as RQQueue
from rq.registry import FailedJobRegistry, StartedJobRegistry

from core import broll_prompts, lektor, supa
from core.contracts import (
    BROLL_KATEGORIEN,
    Bucket,
    Queue as QueueName,
    Source,
    State,
    queue_timeout,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(title="Blaulicht-Leitstand")
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


# ---------------------------------------------------------------------------
# Redis / RQ — eine Queue-Instanz je Pipeline-Stufe, on-demand erzeugt
# ---------------------------------------------------------------------------
_redis: Optional[Redis] = None


def redis_conn() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(os.environ["REDIS_URL"])
    return _redis


def queue(name: QueueName) -> RQQueue:
    """RQ-Queue für eine Pipeline-Stufe. Jobs werden als String-Referenz
    eingereiht (z.B. 'workers.extract.extract') — die api importiert die
    Worker-Module NICHT, RQ löst den Funktionsnamen erst beim Ausführen
    im jeweiligen Worker-Container auf."""
    return RQQueue(name.value, connection=redis_conn(),
                   default_timeout=queue_timeout(name))


# ---------------------------------------------------------------------------
# AUTH — einfache Passwort-Schranke für den MVP
# ---------------------------------------------------------------------------
# TODO(später): durch Supabase Auth ersetzen (Login über SUPABASE_ANON_KEY,
# Rollen/RLS-gestützt). Für den MVP reicht ein geteiltes Passwort — die
# Leitstand-UI ist kein öffentliches Produkt, sondern internes Werkzeug.
LEITSTAND_PASSWORD = os.environ.get("LEITSTAND_PASSWORD", "leitstand")
SESSION_SECRET = os.environ.get("SESSION_SECRET", "blaulicht-mvp-" + LEITSTAND_PASSWORD)
SESSION_COOKIE = "blaulicht_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 14  # 14 Tage

PUBLIC_PATHS = {"/login"}


def _sign(payload: str) -> str:
    mac = hmac.new(SESSION_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).decode("utf-8").rstrip("=")


def make_session_token() -> str:
    payload = str(int(time.time()))
    return f"{payload}.{_sign(payload)}"


def verify_session_token(token: Optional[str]) -> bool:
    if not token or "." not in token:
        return False
    payload, sig = token.rsplit(".", 1)
    if not hmac.compare_digest(_sign(payload), sig):
        return False
    try:
        issued = int(payload)
    except ValueError:
        return False
    return (time.time() - issued) < SESSION_MAX_AGE


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in PUBLIC_PATHS or path.startswith("/static"):
            return await call_next(request)
        if not verify_session_token(request.cookies.get(SESSION_COOKIE)):
            if request.headers.get("HX-Request") == "true":
                resp = HTMLResponse(status_code=286)  # HTMX: HX-Redirect statt Body
                resp.headers["HX-Redirect"] = "/login"
                return resp
            return RedirectResponse("/login", status_code=303)
        return await call_next(request)


app.add_middleware(AuthMiddleware)


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse(request, "login.html", {"error": None})


@app.post("/login", response_class=HTMLResponse)
def login_submit(request: Request, password: str = Form(...)):
    if hmac.compare_digest(password, LEITSTAND_PASSWORD):
        resp = RedirectResponse("/", status_code=303)
        resp.set_cookie(SESSION_COOKIE, make_session_token(), max_age=SESSION_MAX_AGE, httponly=True, samesite="lax")
        return resp
    return templates.TemplateResponse(
        request, "login.html", {"error": "Falsches Passwort."}, status_code=401
    )


@app.post("/logout")
def logout():
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(SESSION_COOKIE)
    return resp


# ---------------------------------------------------------------------------
# Helfer
# ---------------------------------------------------------------------------
def playable_url(bucket: Bucket, path: Optional[str]) -> Optional[str]:
    """Signierte, zeitlich begrenzte URL für einen Storage-Pfad (oder None)."""
    if not path:
        return None
    try:
        return supa.signed_url(bucket, path)
    except Exception:
        return None


def state_label(state: str) -> str:
    labels = {
        State.NEU.value: "Neu",
        State.IN_ANALYSE.value: "In Analyse",
        State.REVIEW.value: "Review",
        State.IN_PRODUKTION.value: "In Produktion",
        State.FERTIG.value: "Fertig",
        State.VEROEFFENTLICHT.value: "Veröffentlicht",
        State.VERWORFEN.value: "Verworfen",
    }
    return labels.get(state, state)


templates.env.filters["state_label"] = state_label


# --- Datum/Zeit deutsch: TT.MM.JJJJ (statt ISO 2026-07-30) -----------------
# Zeitstempel kommen als ISO-String aus Supabase (created_at, UTC) bzw. als
# reines Datum aus der Fakten-Extraktion (facts.datum, YYYY-MM-DD). Beide
# Formen landen hier; unparsbares wird unveraendert durchgereicht statt zu
# knallen (die UI soll nie an einem Datum scheitern).
try:
    from zoneinfo import ZoneInfo
    _TZ: Optional[Any] = ZoneInfo(os.environ.get("TZ", "Europe/Berlin"))
except Exception:                                    # tzdata fehlt im Image
    _TZ = None


def _parse_dt(value: Any) -> Optional[datetime]:
    s = str(value or "").strip()
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def dt_de(value: Any, fallback: str = "—") -> str:
    """ISO-Zeitstempel -> „TT.MM.JJJJ HH:MM" in lokaler Zeit (Europe/Berlin)."""
    d = _parse_dt(value)
    if d is None:
        return str(value) if value else fallback
    if d.tzinfo is not None and _TZ is not None:
        d = d.astimezone(_TZ)
    return d.strftime("%d.%m.%Y %H:%M")


def datum_de(value: Any, fallback: str = "—") -> str:
    """Datum (auch ohne Uhrzeit) -> „TT.MM.JJJJ", ohne Zeitanteil."""
    d = _parse_dt(value)
    if d is None:
        return str(value) if value else fallback
    return d.strftime("%d.%m.%Y")


templates.env.filters["dt_de"] = dt_de
templates.env.filters["datum_de"] = datum_de


def set_config_min_score(value: int) -> None:
    """Persistiert die Score-Schwelle in blaulicht.config (Singleton id=1).
    core.supa bietet dafür bewusst keinen eigenen Helper — wir nutzen den
    öffentlich exportierten supa.client(), ohne core/ selbst zu ändern."""
    from core.contracts import DB_SCHEMA

    supa.client().schema(DB_SCHEMA).table("config").update({"min_score": value}).eq("id", 1).execute()


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, min_score: Optional[int] = None, state: Optional[str] = None):
    cfg = supa.get_config()
    threshold = min_score if min_score is not None else int(cfg.get("min_score", 40))
    cases = supa.list_cases(min_score=threshold, state=state or None)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "cases": cases,
            "min_score": threshold,
            "state": state or "",
            "states": list(State),
            **_status_ctx(),          # Statusband beim ersten Rendern befuellen
        },
    )


@app.get("/partials/cases-table", response_class=HTMLResponse)
def cases_table_partial(request: Request, min_score: int = 40, state: str = ""):
    cases = supa.list_cases(min_score=min_score, state=state or None)
    return templates.TemplateResponse(
        request,
        "partials/cases_table.html",
        {
            "cases": cases,
            "min_score": min_score,
            "state": state,
            "states": list(State),
        },
    )


# ---------------------------------------------------------------------------
# Statusanzeige — was arbeitet gerade? (Kopfzeile im Dashboard, pollt sich selbst)
# ---------------------------------------------------------------------------
QUEUE_LABELS: dict[QueueName, str] = {
    QueueName.INGEST: "Ingest",
    QueueName.EXTRACT: "Fakten",
    QueueName.SCRIPT: "Skript",
    QueueName.TTS: "Stimme",
    QueueName.RENDER: "Render",
    QueueName.PUBLISH: "Publish",
}

# Zustaende, die im Statusband gezaehlt werden (verworfen/veroeffentlicht
# interessieren im laufenden Betrieb nicht — die sind erledigt).
STATUS_STATES = (State.NEU, State.IN_ANALYSE, State.REVIEW,
                 State.IN_PRODUKTION, State.FERTIG)


def _status_ctx() -> dict[str, Any]:
    """Queue-Auslastung + Fallzahlen je Zustand fuer das Statusband.

    Redis-Ausfall darf das Dashboard nicht zerlegen: schlaegt der Zugriff fehl,
    wird das als Fehlermeldung im Band angezeigt statt als 500er-Seite.
    """
    queues: list[dict[str, Any]] = []
    fehler_gesamt = 0
    redis_ok = True
    try:
        conn = redis_conn()
        for qn, label in QUEUE_LABELS.items():
            q = RQQueue(qn.value, connection=conn)
            laufend = len(StartedJobRegistry(queue=q))
            fehler = len(FailedJobRegistry(queue=q))
            fehler_gesamt += fehler
            queues.append({"name": qn.value, "label": label,
                           "wartend": q.count, "laufend": laufend, "fehler": fehler})
    except Exception:
        redis_ok = False

    zustaende: list[dict[str, Any]] = []
    db_ok = True
    try:
        from core.contracts import DB_SCHEMA
        rows = (supa.client().schema(DB_SCHEMA).table("cases")
                .select("state").limit(2000).execute().data or [])
        counts = Counter(r.get("state") for r in rows)
        zustaende = [{"value": s.value, "label": state_label(s.value),
                      "anzahl": counts.get(s.value, 0)} for s in STATUS_STATES]
    except Exception:
        db_ok = False

    aktiv = any(q["laufend"] or q["wartend"] for q in queues)
    return {
        "queues": queues,
        "zustaende": zustaende,
        "aktiv": aktiv,
        "fehler_gesamt": fehler_gesamt,
        "redis_ok": redis_ok,
        "db_ok": db_ok,
        "stand": datetime.now(_TZ).strftime("%H:%M:%S") if _TZ else datetime.now().strftime("%H:%M:%S"),
    }


@app.get("/partials/status", response_class=HTMLResponse)
def status_partial(request: Request):
    return templates.TemplateResponse(request, "partials/statusbar.html", _status_ctx())


@app.post("/config/min-score", response_class=HTMLResponse)
def update_min_score(request: Request, min_score: int = Form(...), state: str = Form("")):
    set_config_min_score(min_score)
    cases = supa.list_cases(min_score=min_score, state=state or None)
    return templates.TemplateResponse(
        request,
        "partials/cases_table.html",
        {
            "cases": cases,
            "min_score": min_score,
            "state": state,
            "states": list(State),
        },
    )


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------
@app.post("/ingest", response_class=HTMLResponse)
def trigger_ingest(request: Request, source: str = Query(...)):
    if source not in {s.value for s in Source}:
        return HTMLResponse(f'<div class="flash flash-error">Unbekannte Quelle „{source}".</div>', status_code=400)
    queue(QueueName.INGEST).enqueue("workers.ingest.ingest", source)
    return HTMLResponse(f'<div class="flash flash-ok">Ingest „{source}" eingereiht.</div>')


# ---------------------------------------------------------------------------
# Fall-Gates
# ---------------------------------------------------------------------------
def _redirect_case(case_id: str) -> RedirectResponse:
    return RedirectResponse(f"/cases/{case_id}", status_code=303)


@app.post("/cases/{case_id}/freigabe-analyse")
def freigabe_analyse(case_id: str):
    supa.set_state(case_id, State.IN_ANALYSE.value)
    queue(QueueName.EXTRACT).enqueue("workers.extract.extract", case_id)
    return _redirect_case(case_id)


@app.post("/cases/{case_id}/retts")
async def retts(case_id: str, request: Request):
    """Skript-Text speichern (spec.scenes[].vo/caption aus dem Formular) +
    neu vertonen (TTS-Job einreihen).

    Formularfelder je Szene: scene_<i>_vo, scene_<i>_caption (editierbar).
    Alle anderen Szenenfelder (role/broll/sfx/t_start/t_end/overlay) kommen
    unverändert als hidden inputs mit, damit spec.scenes strukturell erhalten
    bleibt — nur der gesprochene Text und die Bildschirmtexte ändern sich.
    """
    case = supa.get_case(case_id)
    if not case:
        return RedirectResponse("/", status_code=303)

    spec = dict(case.get("spec") or {})
    scenes = list(spec.get("scenes") or [])
    form = await request.form()

    new_scenes = []
    vo_parts = []
    for i, scene in enumerate(scenes):
        new_scene = dict(scene)
        vo = form.get(f"scene_{i}_vo")
        caption = form.get(f"scene_{i}_caption")
        if vo is not None:
            new_scene["vo"] = str(vo)
        if caption is not None:
            new_scene["caption"] = str(caption)
        new_scenes.append(new_scene)
        if new_scene.get("vo"):
            vo_parts.append(str(new_scene["vo"]))

    spec["scenes"] = new_scenes
    if vo_parts:
        spec["voiceover"] = " ".join(vo_parts)

    supa.update_case(case_id, {"spec": spec})
    queue(QueueName.TTS).enqueue("workers.tts.tts", case_id)
    return RedirectResponse(f"/cases/{case_id}", status_code=303)


@app.post("/cases/{case_id}/freigabe-clip")
def freigabe_clip(case_id: str):
    # State IN_PRODUKTION == "Render läuft" (siehe core.contracts.State) —
    # die api markiert den Start der Arbeit, der render-Worker schaltet am
    # Ende selbst auf FERTIG weiter (Gate „Freigabe Veröffentlichung").
    supa.set_state(case_id, State.IN_PRODUKTION.value)
    queue(QueueName.RENDER).enqueue("workers.render.render", case_id)
    return _redirect_case(case_id)


@app.post("/cases/{case_id}/freigabe-veroeffentlichung")
def freigabe_veroeffentlichung(case_id: str):
    queue(QueueName.PUBLISH).enqueue("workers.publish.publish", case_id)
    return _redirect_case(case_id)


@app.post("/cases/{case_id}/verwerfen")
def verwerfen(case_id: str):
    supa.set_state(case_id, State.VERWORFEN.value)
    return RedirectResponse("/", status_code=303)


# ---------------------------------------------------------------------------
# Review-Detailseite
# ---------------------------------------------------------------------------
@app.get("/cases/{case_id}", response_class=HTMLResponse)
def case_detail(request: Request, case_id: str):
    case = supa.get_case(case_id)
    if not case:
        return HTMLResponse("Fall nicht gefunden.", status_code=404)
    facts = case.get("facts") or {}
    spec = case.get("spec") or {}
    scenes = spec.get("scenes") or []
    voice_url = playable_url(Bucket.VOICE, case.get("voice_url"))
    video_url = playable_url(Bucket.RENDERS, case.get("video_url"))
    # Lesbarkeits-Ampel je Szene — rein informativ, aendert nichts am Text.
    lesbarkeit = [lektor.lesbarkeit(sc.get("vo") or "") for sc in scenes]
    return templates.TemplateResponse(
        request,
        "case_detail.html",
        {
            "case": case,
            "facts": facts,
            "spec": spec,
            "scenes": scenes,
            "lesbarkeit": lesbarkeit,
            "voice_url": voice_url,
            "video_url": video_url,
            "states": list(State),
        },
    )


@app.post("/cases/{case_id}/lektor", response_class=HTMLResponse)
def lektor_vorschlag(request: Request, case_id: str):
    """Umschreib-Vorschlag fuer die Sprechtexte bauen (HTMX-Partial).

    Speichert NICHTS — das Ergebnis ist ein Formular auf das bestehende
    /retts, das der Mensch vor dem Absenden noch bearbeiten kann.
    """
    case = supa.get_case(case_id)
    if not case:
        return HTMLResponse('<div class="flash flash-error">Fall nicht gefunden.</div>', status_code=404)
    scenes = (case.get("spec") or {}).get("scenes") or []
    if not scenes:
        return HTMLResponse('<div class="flash flash-error">Noch kein Skript vorhanden.</div>')
    try:
        vorschlaege = lektor.lektoriere(scenes)
    except Exception as exc:                      # Claude nicht erreichbar o. ä.
        return HTMLResponse(
            f'<div class="flash flash-error">Lektor fehlgeschlagen: {exc}</div>')
    return templates.TemplateResponse(
        request,
        "partials/lektor_vorschlag.html",
        {"case": case, "scenes": scenes, "vorschlaege": vorschlaege},
    )


@app.get("/cases/{case_id}/partials/status", response_class=HTMLResponse)
def case_status_partial(request: Request, case_id: str):
    case = supa.get_case(case_id)
    if not case:
        return HTMLResponse('<span class="badge badge-error">nicht gefunden</span>', status_code=404)
    return templates.TemplateResponse(request, "partials/status_badge.html", {"case": case})


@app.get("/cases/{case_id}/partials/media", response_class=HTMLResponse)
def case_media_partial(request: Request, case_id: str):
    case = supa.get_case(case_id)
    if not case:
        return HTMLResponse("", status_code=404)
    voice_url = playable_url(Bucket.VOICE, case.get("voice_url"))
    video_url = playable_url(Bucket.RENDERS, case.get("video_url"))
    return templates.TemplateResponse(
        request,
        "partials/media_panel.html",
        {"case": case, "voice_url": voice_url, "video_url": video_url},
    )


# ---------------------------------------------------------------------------
# B-Roll-Verwaltung
# ---------------------------------------------------------------------------
_BROLL_NN_RE = re.compile(r"^broll_(?P<kat>[a-z]+)_(?P<nn>\d+)\.")


def _next_broll_name(kategorie: str, ext: str) -> str:
    existing = supa.list_broll()
    max_nn = 0
    for name in existing:
        m = _BROLL_NN_RE.match(name)
        if m and m.group("kat") == kategorie:
            max_nn = max(max_nn, int(m.group("nn")))
    return f"broll_{kategorie}_{max_nn + 1:02d}{ext}"


# Kontext fuer den Prompt-Generator (Auswahllisten aus core.broll_prompts —
# der Single Source of Truth; die fixen Bloecke selbst bleiben im core-Modul).
def _prompt_generator_ctx() -> dict[str, Any]:
    return {
        "pg_beleuchtung": broll_prompts.BELEUCHTUNG,
        "pg_zustand": broll_prompts.ZUSTAND,
        "pg_umfeld": broll_prompts.UMFELD,
        "pg_bewegung": broll_prompts.KAMERABEWEGUNG,
        "pg_subjekt": broll_prompts.SUBJEKT,
        "pg_master": broll_prompts.MASTER_PRESETS,
        "pg_kategorien": broll_prompts.KATEGORIE_PRESETS,
        "pg_workflow": broll_prompts.WORKFLOW_HINWEIS,
    }


@app.get("/broll", response_class=HTMLResponse)
def broll_page(request: Request):
    files = supa.list_broll()
    return templates.TemplateResponse(
        request,
        "broll.html",
        {"files": files, "kategorien": BROLL_KATEGORIEN, "error": None,
         **_prompt_generator_ctx()},
    )


@app.get("/broll/prompt", response_class=HTMLResponse)
def broll_prompt(request: Request,
                 motiv: str = Query("automat"),
                 zustand: str = Query("intakt_nacht"),
                 umfeld: str = Query("wand"),
                 beleuchtung: str = Query("nacht_laterne"),
                 bewegung: str = Query("keine"),
                 preset: Optional[str] = Query(None),
                 kategorie: Optional[str] = Query(None)):
    """Fertigen Higgsfield-Prompt bauen (HTMX-Partial fuer die /broll-Seite).

    Drei Wege: Master-Preset (?preset=...), Kategorie-Preset (?kategorie=...,
    liefert die zur Szenen-Rolle passende Kombination + Upload-Hinweis) oder
    die freie Kombination aus den Dropdowns. motiv='automat' nutzt den fixen
    [Automat]-Block; jeder andere Wert ist ein broll_prompts.SUBJEKT-Schluessel."""
    ziel_kategorie = None
    try:
        if preset:
            prompt = broll_prompts.build_master_prompt(preset)
        elif kategorie:
            prompt = broll_prompts.build_kategorie_prompt(kategorie)
            ziel_kategorie = kategorie
        elif motiv == "automat":
            prompt = broll_prompts.build_prompt(
                beleuchtung=beleuchtung, zustand=zustand, umfeld=umfeld,
                kamerabewegung=bewegung)
        else:
            prompt = broll_prompts.build_prompt(
                beleuchtung=beleuchtung, subjekt=motiv, kamerabewegung=bewegung)
        error = None
    except ValueError as e:
        prompt, error = "", str(e)
    return templates.TemplateResponse(
        request,
        "partials/prompt_out.html",
        {"prompt": prompt, "error": error, "ziel_kategorie": ziel_kategorie},
    )


@app.post("/broll", response_class=HTMLResponse)
async def broll_upload(request: Request, kategorie: str = Form(...), file: UploadFile = File(...)):
    if kategorie not in BROLL_KATEGORIEN:
        files = supa.list_broll()
        return templates.TemplateResponse(
            request,
            "broll.html",
            {
                "files": files,
                "kategorien": BROLL_KATEGORIEN,
                "error": f'Unbekannte Kategorie „{kategorie}".',
            },
            status_code=400,
        )

    ext = os.path.splitext(file.filename or "")[1].lower() or ".mp4"
    target_name = _next_broll_name(kategorie, ext)

    fd, tmp_path = tempfile.mkstemp(suffix=ext)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(await file.read())
        supa.upload(Bucket.BROLL, target_name, tmp_path, content_type=file.content_type or "video/mp4")
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass

    files = supa.list_broll()
    return templates.TemplateResponse(
        request,
        "broll.html",
        {"files": files, "kategorien": BROLL_KATEGORIEN, "error": None},
    )
