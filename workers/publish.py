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
from typing import Any, Optional

from core.contracts import Bucket, State
from core.supa import get_case, update_case, set_state, signed_url


# ---------------------------------------------------------------------------
# Hauptjob (RQ-Queue "publish")
# ---------------------------------------------------------------------------
def publish(case_id: str, platform: str = "download") -> dict[str, Any]:
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
