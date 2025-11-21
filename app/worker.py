from __future__ import annotations

from typing import Dict, Optional

from rq import get_current_job

from .job_utils import format_result
from .services.analysis_pipeline import analyze_messages, fetch_chat_messages


def run_analysis_job(
    url: str,
    keyword: Optional[str],
    chat_config: Dict,
    youtube_config: Dict,
    cps_config: Dict,
    spike_config: Dict,
) -> Dict:
    job = get_current_job()
    _update_meta(
        job,
        status="running",
        processed_messages=0,
        last_timestamp=None,
        keyword=keyword,
    )

    def progress_callback(processed: int, last_timestamp: float | None) -> None:
        _update_meta(
            job,
            status="running",
            processed_messages=processed,
            last_timestamp=last_timestamp,
        )

    try:
        messages = fetch_chat_messages(
            url=url,
            chat_config=chat_config,
            youtube_config=youtube_config,
            progress_callback=progress_callback,
        )
        total_data = analyze_messages(messages, None, cps_config, spike_config)
        result_total = format_result(url, total_data)

        result_keyword = None
        if keyword:
            keyword_data = analyze_messages(messages, keyword, cps_config, spike_config)
            result_keyword = format_result(url, keyword_data)

        payload = {
            "result_total": result_total,
            "result_keyword": result_keyword,
            "messages": messages,
            "url": url,
        }
        _update_meta(
            job,
            status="completed",
            result_total=result_total,
            result_keyword=result_keyword,
        )
        return payload
    except ValueError as exc:
        _update_meta(job, status="error", error=str(exc))
        raise
    except Exception:  # pylint: disable=broad-except
        _update_meta(job, status="error", error="解析中にエラーが発生しました。")
        raise


def _update_meta(job, **fields) -> None:
    if not job:
        return
    meta = job.meta or {}
    meta.update(fields)
    job.meta = meta
    job.save_meta()
