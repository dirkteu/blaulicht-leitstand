# -*- coding: utf-8 -*-
"""
core/supa.py  —  gemeinsamer Supabase-Zugriff (DB + Storage)
============================================================

Ein Client für alle Services. Serverseitig mit dem service_role-Key (umgeht RLS).
Tabellen liegen im Schema `blaulicht` (siehe contracts.DB_SCHEMA).

Storage-Regel (nach dem Datenverlust): der `broll`-Bucket wird NUR gelesen.
Es gibt hier bewusst KEINE Lösch-/Überschreib-Helfer für broll.
"""

from __future__ import annotations
import os
import tempfile
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from supabase import create_client, Client
from .contracts import DB_SCHEMA, Bucket

_client: Optional[Client] = None


def client() -> Client:
    global _client
    if _client is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_SERVICE_KEY"]
        _client = create_client(url, key)
    return _client


def _tbl(name: str):
    return client().schema(DB_SCHEMA).table(name)


# ---------------------------------------------------------------------------
# Fälle (cases)
# ---------------------------------------------------------------------------
def insert_case(data: dict[str, Any]) -> dict[str, Any]:
    """Neuen Fall anlegen; bei doppeltem Link (unique) wird ignoriert."""
    res = _tbl("cases").upsert(data, on_conflict="link", ignore_duplicates=True).execute()
    return res.data[0] if res.data else {}


def get_case(case_id: str) -> Optional[dict[str, Any]]:
    res = _tbl("cases").select("*").eq("id", case_id).limit(1).execute()
    return res.data[0] if res.data else None


def update_case(case_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    res = _tbl("cases").update(patch).eq("id", case_id).execute()
    return res.data[0] if res.data else {}


def set_state(case_id: str, state: str, error: Optional[str] = None) -> None:
    """Zustand setzen. `error` wird IMMER mitgeschrieben — ohne Angabe also auf
    NULL zurueckgesetzt.

    Vorher wurde das Feld nur im Fehlerfall geschrieben und blieb bei Erfolg
    stehen. Ein Fall, der nach einem fehlgeschlagenen Versuch beim zweiten Mal
    durchlief, schleppte die alte Meldung mit und erzeugte im Leitstand ein ⚠,
    obwohl nichts im Argen war (beobachtet 01.08.2026 an fcaa7933: Zustand
    `review`, Tonspur vorhanden, trotzdem die 429-Meldung vom 30.07. im Feld).

    Alle Aufrufer ohne `error=` sind Erfolgspfade — geprueft in workers/tts.py,
    render.py und publish.py.
    """
    _tbl("cases").update({"state": state, "error": error}).eq("id", case_id).execute()


def list_cases(min_score: int = 0, state: Optional[str] = None, limit: int = 200,
               include_verworfen: bool = False) -> list[dict[str, Any]]:
    """Faelle ab Score-Schwelle, nach Score sortiert. Ohne expliziten `state`
    werden VERWORFEN-Faelle standardmaessig ausgeblendet (aufgeraeumte Ansicht);
    mit `state='verworfen'` oder `include_verworfen=True` sind sie sichtbar."""
    q = _tbl("cases").select("*").gte("score", min_score).order("score", desc=True).limit(limit)
    if state:
        q = q.eq("state", state)
    elif not include_verworfen:
        q = q.neq("state", "verworfen")
    return q.execute().data or []


def recent_cases(days: int = 10) -> list[dict[str, Any]]:
    """Lebende Faelle (state != verworfen) der letzten `days` Tage — schlanke
    Auswahl fuer den quellen-uebergreifenden Ingest-Dedup (workers/ingest.py)."""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    return (_tbl("cases")
            .select("id,title,ort,tat,source,created_at,state")
            .neq("state", "verworfen")
            .gte("created_at", since)
            .limit(500)
            .execute().data or [])


# ---------------------------------------------------------------------------
# Einstellungen (config, Singleton id=1)
# ---------------------------------------------------------------------------
def get_config() -> dict[str, Any]:
    res = _tbl("config").select("*").eq("id", 1).limit(1).execute()
    return res.data[0] if res.data else {"min_score": 40, "ingest_times": "07:00,19:00", "aussprache": {}}


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------
def upload(bucket: Bucket, path: str, local_file: str, content_type: str = "application/octet-stream") -> None:
    with open(local_file, "rb") as f:
        client().storage.from_(bucket.value).upload(
            path, f.read(), {"content-type": content_type, "upsert": "true"})


def download(bucket: Bucket, path: str) -> str:
    """Datei in eine Temp-Datei laden und deren Pfad zurückgeben (nur lesen)."""
    data = client().storage.from_(bucket.value).download(path)
    suffix = os.path.splitext(path)[1] or ".bin"
    fd, tmp = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    return tmp


def signed_url(bucket: Bucket, path: str, expires_in: int = 3600) -> str:
    res = client().storage.from_(bucket.value).create_signed_url(path, expires_in)
    return res.get("signedURL") or res.get("signed_url") or ""


def list_broll() -> list[str]:
    """Dateinamen im broll-Bucket (für die Szenen-Auswahl)."""
    items = client().storage.from_(Bucket.BROLL.value).list()
    return [it["name"] for it in items if it.get("name", "").endswith(".mp4")]
