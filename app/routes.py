from __future__ import annotations

from typing import Dict
from uuid import uuid4

from flask import Blueprint, Flask, current_app, jsonify, render_template, request
from redis import Redis
from rq import Queue
from rq.exceptions import NoSuchJobError
from rq.job import Job

from .job_utils import format_result
from .services.analysis_pipeline import analyze_messages


def register_routes(app: Flask) -> None:
    bp = Blueprint("main", __name__)

    @bp.get("/")
    def index():
        return render_template("index.html")

    @bp.post("/analyze/start")
    def start_analysis():
        payload = request.get_json(silent=True) or request.form
        url = (payload.get("url") or "").strip()
        keyword = (payload.get("keyword") or "").strip() or None
        if not url:
            return jsonify({"error": "URL is required"}), 400

        job_id = str(uuid4())
        queue = _get_queue()
        redis_cfg = current_app.config["REDIS"]
        job = queue.enqueue(
            "app.worker.run_analysis_job",
            kwargs={
                "url": url,
                "keyword": keyword,
                "chat_config": current_app.config["CHATDOWNLOADER"],
                "youtube_config": current_app.config.get("YOUTUBE", {}),
                "cps_config": current_app.config["CPS"],
                "spike_config": current_app.config["SPIKE_DETECTION"],
            },
            job_id=job_id,
            result_ttl=redis_cfg["result_ttl"],
            meta={
                "status": "queued",
                "processed_messages": 0,
                "last_timestamp": None,
                "keyword": keyword,
            },
        )

        return jsonify({"job_id": job.id})

    @bp.get("/analyze/status/<job_id>")
    def job_status(job_id: str):
        job = _fetch_job(job_id)
        if not job:
            return jsonify({"error": "job not found"}), 404
        return jsonify(_serialize_job(job))

    @bp.post("/analyze/recompute/<job_id>")
    def recompute(job_id: str):
        payload = request.get_json(silent=True) or request.form
        keyword = (payload.get("keyword") or "").strip() or None
        job = _fetch_job(job_id)
        if job is None:
            return jsonify({"error": "job not found"}), 404
        if job.get_status() != "finished":
            return jsonify({"error": "job not ready"}), 400

        job_payload = job.result or {}
        messages = job_payload.get("messages")
        job_url = job_payload.get("url")
        if not messages or not job_url:
            return jsonify({"error": "job payload missing"}), 400

        cps_config = current_app.config["CPS"]
        spike_config = current_app.config["SPIKE_DETECTION"]
        data = analyze_messages(messages, keyword, cps_config, spike_config)
        result = format_result(job_url, data)
        meta = job.meta or {}
        meta.update({"result_keyword": result, "keyword": keyword})
        job.meta = meta
        job.save_meta()
        return jsonify({"result": result})

    app.register_blueprint(bp)


def _redis_connection() -> Redis:
    redis_cfg = current_app.config["REDIS"]
    return Redis.from_url(redis_cfg["url"])


def _get_queue() -> Queue:
    redis_cfg = current_app.config["REDIS"]
    return Queue(
        redis_cfg["queue_name"],
        connection=_redis_connection(),
        default_timeout=redis_cfg["job_timeout"],
    )


def _fetch_job(job_id: str) -> Job | None:
    try:
        return Job.fetch(job_id, connection=_redis_connection())
    except NoSuchJobError:
        return None


def _serialize_job(job: Job) -> Dict:
    meta = job.meta or {}
    job_status = meta.get("status") or job.get_status()
    status = _map_status(job_status or job.get_status())
    payload: Dict = {
        "job_id": job.id,
        "status": status,
        "processed_messages": meta.get("processed_messages", 0),
        "last_timestamp": meta.get("last_timestamp"),
        "keyword": meta.get("keyword"),
        "error": meta.get("error"),
    }
    if status == "completed":
        result = job.result or {}
        payload["result_total"] = result.get("result_total") or meta.get("result_total")
        payload["result_keyword"] = result.get("result_keyword") or meta.get(
            "result_keyword"
        )
    return payload


def _map_status(raw_status: str | None) -> str:
    if raw_status in {"queued", "scheduled"}:
        return "queued"
    if raw_status in {"started", "running"}:
        return "running"
    if raw_status in {"finished", "completed"}:
        return "completed"
    if raw_status in {"failed", "error"}:
        return "error"
    return raw_status or "queued"
