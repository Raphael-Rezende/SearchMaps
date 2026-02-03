import os
import threading
import uuid
import re
import unicodedata
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

from core import run_search
from exporter import export_results

DEMO_MAX_LIMIT = int(os.getenv("SEARCHMAPS_DEMO_MAX_LIMIT", "10"))
MAX_QUEUE_JOBS = int(os.getenv("SEARCHMAPS_MAX_QUEUE_JOBS", "2"))
RATE_LIMIT_SECONDS = int(os.getenv("SEARCHMAPS_RATE_LIMIT_SECONDS", "60"))

JOBS: Dict[str, Dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()
RUN_LOCK = threading.Lock()
LAST_REQUEST_BY_IP: Dict[str, datetime] = {}


class QueueFullError(Exception):
    pass


class RateLimitError(Exception):
    pass


class LimitExceededError(ValueError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_text(value: Optional[str]) -> str:
    if not value:
        return ""
    value = value.strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"[^\w\s]", "", value)
    return value


def _normalize_phone(value: Optional[str]) -> str:
    if not value:
        return ""
    return re.sub(r"\D", "", value)


def _dedupe_results(results: List[Dict[str, str]], limit: Optional[int]) -> List[Dict[str, str]]:
    seen = set()
    deduped = []

    for item in results:
        name = _normalize_text(item.get("name"))
        address = _normalize_text(item.get("address"))
        key = f"{name}|{address}" if name and address else ""

        if not key:
            phone = _normalize_phone(item.get("phone"))
            if phone:
                key = f"phone:{phone}"

        if key and key in seen:
            continue
        if key:
            seen.add(key)

        deduped.append(item)
        if limit and len(deduped) >= limit:
            break

    return deduped


def _update_job(job_id: str, **fields: Any) -> None:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return
        job.update(fields)


def _get_job(job_id: str) -> Optional[Dict[str, Any]]:
    with JOBS_LOCK:
        return JOBS.get(job_id)


def _is_canceled(job_id: str) -> bool:
    job = _get_job(job_id)
    return bool(job and job.get("status") == "canceled")


def _count_active_jobs() -> Tuple[int, int]:
    queued = 0
    running = 0
    for job in JOBS.values():
        status = job.get("status")
        if status == "queued":
            queued += 1
        elif status == "running":
            running += 1
    return queued, running


def _check_queue_capacity() -> None:
    queued, running = _count_active_jobs()
    max_active = MAX_QUEUE_JOBS + 1  # 1 rodando + fila
    if queued >= MAX_QUEUE_JOBS or (queued + running) >= max_active:
        raise QueueFullError(
            "A fila da DEMO está cheia no momento. Aguarde alguns minutos e tente novamente."
        )


def _check_rate_limit(client_ip: Optional[str]) -> None:
    if not client_ip:
        return
    now = datetime.now(timezone.utc)
    last = LAST_REQUEST_BY_IP.get(client_ip)
    if last:
        elapsed = (now - last).total_seconds()
        if elapsed < RATE_LIMIT_SECONDS:
            remaining = int(RATE_LIMIT_SECONDS - elapsed)
            remaining = max(1, remaining)
            raise RateLimitError(
                f"Você acabou de iniciar uma busca. Aguarde {remaining}s para tentar novamente."
            )
    LAST_REQUEST_BY_IP[client_ip] = now


def create_job(
    city: str,
    query: str,
    state: Optional[str],
    limit: Optional[int],
    client_ip: Optional[str] = None,
) -> str:
    job_id = uuid.uuid4().hex
    effective_limit = limit or DEMO_MAX_LIMIT

    if effective_limit > DEMO_MAX_LIMIT:
        raise LimitExceededError(
            f"Na DEMO o limite máximo é {DEMO_MAX_LIMIT} resultados por busca. "
            "Reduza o limite e tente novamente."
        )

    effective_limit = max(1, min(effective_limit, DEMO_MAX_LIMIT))

    job = {
        "status": "queued",
        "progress": 0,
        "message": "Na fila.",
        "params": {"city": city, "query": query, "state": state, "limit": effective_limit},
        "results": [],
        "createdAt": _now_iso(),
        "error": None,
    }

    with JOBS_LOCK:
        _check_queue_capacity()
        _check_rate_limit(client_ip)
        JOBS[job_id] = job

    thread = threading.Thread(target=_run_job, args=(job_id,), daemon=True)
    thread.start()

    return job_id


def _run_job(job_id: str) -> None:
    with RUN_LOCK:
        job = _get_job(job_id)
        if not job:
            return

        if _is_canceled(job_id):
            _update_job(job_id, message="Cancelado.")
            return

        try:
            _update_job(job_id, status="running", progress=5, message="Inicializando job...")
            if _is_canceled(job_id):
                _update_job(job_id, message="Cancelado.")
                return

            _update_job(job_id, progress=15, message="Abrindo Google Maps...")
            if _is_canceled(job_id):
                _update_job(job_id, message="Cancelado.")
                return

            _update_job(job_id, progress=30, message="Buscando resultados...")
            if _is_canceled(job_id):
                _update_job(job_id, message="Cancelado.")
                return

            params = job.get("params", {})
            city = params.get("city")
            query = params.get("query")
            state = params.get("state")
            limit = params.get("limit")

            def progress_cb(collected: int, limit_value: Optional[int]) -> None:
                if _is_canceled(job_id):
                    return
                if limit_value:
                    ratio = min(collected / max(limit_value, 1), 1)
                    progress = 60 + int(ratio * 20)
                    message = f"Coletando dados... ({collected}/{limit_value})"
                else:
                    progress = 60
                    message = f"Coletando dados... ({collected})"
                _update_job(job_id, progress=progress, message=message)

            def should_cancel() -> bool:
                return _is_canceled(job_id)

            results = run_search(
                city=city,
                query=query,
                state=state,
                limit=limit,
                progress_cb=progress_cb,
                should_cancel=should_cancel,
            )

            if _is_canceled(job_id):
                _update_job(job_id, message="Cancelado.")
                return

            _update_job(job_id, progress=85, message="Finalizando deduplicação...")
            deduped = _dedupe_results(results, limit)

            _update_job(
                job_id,
                status="done",
                progress=100,
                message="Concluído.",
                results=deduped,
                error=None,
            )
        except Exception as exc:
            print(f"[ERRO] Job {job_id} falhou: {exc}")
            _update_job(
                job_id,
                status="error",
                progress=100,
                message="Erro durante a execução.",
                error=(
                    "Não foi possível concluir a busca. O Google Maps pode ter demorado para responder. "
                    "Tente novamente com menos resultados ou aguarde alguns minutos."
                ),
            )


def get_status(job_id: str) -> Optional[Dict[str, Any]]:
    job = _get_job(job_id)
    if not job:
        return None

    return {
        "status": job.get("status"),
        "progress": job.get("progress"),
        "message": job.get("message"),
        "error": job.get("error"),
    }


def get_results(job_id: str) -> Optional[Dict[str, Any]]:
    job = _get_job(job_id)
    if not job:
        return None

    results = job.get("results", [])
    return {"results": results, "total": len(results)}


def export_job(job_id: str, fmt: str) -> Optional[Dict[str, str]]:
    job = _get_job(job_id)
    if not job:
        return None

    results = job.get("results", [])
    if not results:
        raise ValueError("Nenhum resultado para exportar.")
    filename, _path = export_results(results, job_id, fmt)
    return {"filename": filename}


def cancel_job(job_id: str) -> bool:
    job = _get_job(job_id)
    if not job:
        return False

    _update_job(job_id, status="canceled", progress=100, message="Cancelado pelo usuário.")
    return True