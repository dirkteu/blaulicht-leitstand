# -*- coding: utf-8 -*-
"""
workers/publish.py  —  Veröffentlichung vorbereiten (Team 5)
==============================================================

WICHTIG — Freigabe-Gate (core.contracts.NEXT_QUEUE[Queue.PUBLISH] = None):
Diese Funktion wird NUR aufgerufen, nachdem ein Mensch im Leitstand auf
"Veröffentlichen" geklickt hat (api reiht den publish-Job erst nach dem
Klick ein). Sie postet NIE automatisch auf einer Plattform. Das MVP macht
für die eigentliche Distribution absichtlich noch nichts weiter, als eine
signierte Download-URL bereitzustellen — der Mensch lädt den Clip selbst
herunter und postet ihn manuell (siehe UMSETZUNG.md: "Veröffentlichung
zuerst manueller Download").

Die publish_<plattform>(...)-Funktionen unten sind bewusst nur Stubs für
eine spätere Ausbaustufe (echte API-Anbindung). Sie werden von publish()
NICHT aufgerufen, solange platform='download' (Default/MVP).
"""

from __future__ import annotations
import os
from datetime import datetime, timezone
from typing import Any, Optional

from core.contracts import Bucket, State
from core.supa import get_case, update_case, set_state, signed_url


# ---------------------------------------------------------------------------
# Guardrail: Mindest-Alter vor Veröffentlichung (Unschuldsvermutung /
# Ermittlungs-Peak). Frische Taten NICHT sofort veröffentlichen. Steuerbar über
# ENV MIN_PUBLISH_AGE_HOURS (Default 48 h; 0 = Gate aus). Alter = Tatdatum
# (facts.datum), sonst created_at (Ingest ≈ Meldungszeitpunkt) als Näherung.
# ---------------------------------------------------------------------------
def _min_publish_age_hours() -> int:
    try:
        return int(os.environ.get("MIN_PUBLISH_AGE_HOURS", "48"))
    except ValueError:
        return 48


def _parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _case_age_hours(case: dict[str, Any]) -> Optional[float]:
    """Alter des Falls in Stunden, oder None wenn kein Datum bestimmbar."""
    facts = case.get("facts") or {}
    dt = _parse_dt(facts.get("datum")) or _parse_dt(case.get("created_at"))
    if dt is None:
        return None
    return (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0


# ---------------------------------------------------------------------------
# Hauptjob (RQ-Queue "publish")
# ---------------------------------------------------------------------------
def publish(case_id: str, platform: str = "download", force: bool = False) -> dict[str, Any]:
    """Bereitet die Veröffentlichung eines fertigen Falls vor.

    MVP-Verhalten (platform="download", Default):
      1. Fall laden, video_url prüfen (render muss abgeschlossen sein).
      2. Signierte Download-URL für den fertigen Clip erzeugen
         (Bucket.RENDERS, case["video_url"]).
      3. Caption + Hashtags aus case["spec"]["meta"] zusammenstellen.
      4. Beides in case.platform_ids ablegen (nicht überschreiben, mergen).
      5. set_state(case_id, State.VEROEFFENTLICHT) — Endzustand.

    Kein echtes Auto-Posten. Für platform in {"tiktok","youtube","instagram"}
    wird (noch) NICHTS implementiert — siehe Stubs unten; stattdessen landet
    ein klarer Hinweis in platform_ids, dass der Schritt manuell zu erledigen
    ist, damit die UI/den Nutzer nicht im Unklaren lässt.

    Aufrufer-Vertrag: wird ausschließlich vom Freigabe-Gate "Freigabe
    Veröffentlichung" ausgelöst (api reiht den Job erst nach Klick ein,
    core.contracts.NEXT_QUEUE[Queue.PUBLISH] ist None -> kein Auto-Folgejob).
    """
    case = get_case(case_id)
    if not case:
        raise ValueError(f"Fall {case_id} nicht gefunden")

    video_url = case.get("video_url")
    if not video_url:
        # Render war noch nicht erfolgreich / kein Clip vorhanden -> Fehler
        # zurückmelden statt einen Fall ohne Clip als "veroeffentlicht" zu markieren.
        set_state(case_id, State.FERTIG.value, error="publish: kein video_url vorhanden")
        raise ValueError(f"Fall {case_id} hat keinen fertigen Clip (video_url fehlt)")

    # Guardrail: Mindest-Alter (Ermittlungs-Peak/Unschuldsvermutung). Bewusster
    # Override via force=True (z. B. späterer „Trotzdem veröffentlichen"-Button)
    # oder MIN_PUBLISH_AGE_HOURS=0 in .env.
    min_age = _min_publish_age_hours()
    if not force and min_age > 0:
        age = _case_age_hours(case)
        if age is not None and age < min_age:
            msg = (f"guardrail: Fall erst {age:.0f} h alt (< {min_age} h Mindestalter) "
                   f"— Veröffentlichung während des Ermittlungs-Peaks blockiert. "
                   f"In ~{min_age - age:.0f} h erneut versuchen, oder "
                   f"MIN_PUBLISH_AGE_HOURS in .env senken.")
            set_state(case_id, State.FERTIG.value, error=msg)
            raise ValueError(msg)

    result: dict[str, Any] = {"platform": platform}

    if platform == "download":
        result["download_url"] = signed_url(Bucket.RENDERS, video_url)
        result.update(_caption_und_hashtags(case))
    elif platform in ("tiktok", "youtube", "instagram"):
        # Bewusst kein Aufruf von publish_<plattform>() hier -> nicht implementiert.
        # Signierte Download-URL trotzdem bereitstellen, damit ein Mensch den
        # Clip notfalls manuell hochladen kann.
        result["download_url"] = signed_url(Bucket.RENDERS, video_url)
        result.update(_caption_und_hashtags(case))
        result["hinweis"] = (
            f"Auto-Posten fuer '{platform}' ist NICHT implementiert (Stub, siehe "
            f"publish_{platform}() in workers/publish.py). Clip manuell posten."
        )
    else:
        raise ValueError(f"Unbekannte Plattform: {platform}")

    # platform_ids mergen statt überschreiben (spätere Aufrufe/andere Plattformen
    # sollen sich nicht gegenseitig löschen).
    platform_ids = dict(case.get("platform_ids") or {})
    platform_ids[platform] = result
    update_case(case_id, {"platform_ids": platform_ids})

    set_state(case_id, State.VEROEFFENTLICHT.value)
    return result


def _caption_und_hashtags(case: dict[str, Any]) -> dict[str, Any]:
    """Caption/Hashtags/Titel-Optionen aus case['spec']['meta'] ziehen (falls vorhanden)."""
    spec = case.get("spec") or {}
    meta = spec.get("meta") or {}
    return {
        "caption": meta.get("caption", ""),
        "hashtags": meta.get("hashtags", []),
        "title_options": meta.get("title_options", []),
        "hook_line": meta.get("hook_line", ""),
    }


# ---------------------------------------------------------------------------
# Stubs für spätere Plattform-APIs (NICHT implementiert, NICHT von publish()
# aufgerufen). Jede Funktion braucht eigene Tokens/Zugangsdaten via ENV,
# siehe .env.example ("Veröffentlichung (später)").
# ---------------------------------------------------------------------------
def publish_tiktok(case: dict[str, Any], video_path: str) -> dict[str, Any]:
    """STUB — TikTok Content Posting API.

    TODO (spätere Ausbaustufe, NICHT für MVP):
      - OAuth2-Flow / Access Token via TIKTOK_TOKEN (ENV, s. .env.example)
      - Direct Post API: https://developers.tiktok.com/doc/content-posting-api-get-started
      - Upload des Clips (video_url/signed_url) + caption + hashtags aus spec.meta
      - Rückgabe: {"post_id": ..., "share_url": ...}
    Aktuell absichtlich nicht implementiert -> ruft NIE echtes Posten aus.
    """
    raise NotImplementedError(
        "publish_tiktok ist ein Stub. Erfordert TIKTOK_TOKEN (ENV) + TikTok "
        "Content Posting API-Integration. Wird von publish() nicht aufgerufen."
    )


def publish_youtube(case: dict[str, Any], video_path: str) -> dict[str, Any]:
    """STUB — YouTube Data API v3 (Shorts-Upload).

    TODO (spätere Ausbaustufe, NICHT für MVP):
      - OAuth2 (Google) / Refresh Token via YOUTUBE_TOKEN (ENV, s. .env.example)
      - videos.insert (Resumable Upload), Titel aus spec.meta.title_options[0],
        Beschreibung aus caption + hashtags, categoryId, privacyStatus
      - Rückgabe: {"video_id": ..., "url": ...}
    Aktuell absichtlich nicht implementiert -> ruft NIE echtes Posten aus.
    """
    raise NotImplementedError(
        "publish_youtube ist ein Stub. Erfordert YOUTUBE_TOKEN (ENV) + YouTube "
        "Data API v3-Integration. Wird von publish() nicht aufgerufen."
    )


def publish_instagram(case: dict[str, Any], video_path: str) -> dict[str, Any]:
    """STUB — Instagram Graph API (Reels-Publishing).

    TODO (spätere Ausbaustufe, NICHT für MVP):
      - Meta-App + Access Token via INSTAGRAM_TOKEN (ENV, s. .env.example),
        Business-Account erforderlich
      - Container erstellen (media_type=REELS, video_url=signed_url) ->
        Status pollen -> media_publish
      - Caption aus spec.meta.caption + hashtags
      - Rückgabe: {"media_id": ..., "permalink": ...}
    Aktuell absichtlich nicht implementiert -> ruft NIE echtes Posten aus.
    """
    raise NotImplementedError(
        "publish_instagram ist ein Stub. Erfordert INSTAGRAM_TOKEN (ENV) + "
        "Instagram Graph API-Integration. Wird von publish() nicht aufgerufen."
    )
