from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.config import load_app_config
from app.services.analysis_pipeline import analyze_messages, fetch_chat_messages
from app.routes import build_jump_url


def main() -> None:
    parser = argparse.ArgumentParser(description="YouTube コメントスパイク解析サンプル CLI")
    parser.add_argument("url", help="YouTube 動画 URL")
    parser.add_argument("-k", "--keyword", help="キーワードフィルタ", default=None)
    parser.add_argument("--config", help="設定ファイルパス", default=None)
    args = parser.parse_args()

    config_path = Path(args.config) if args.config else None
    app_config = load_app_config(config_path=config_path)

    messages = fetch_chat_messages(
        url=args.url,
        chat_config=app_config["CHATDOWNLOADER"],
        youtube_config=app_config.get("YOUTUBE", {}),
    )
    result = analyze_messages(
        messages=messages,
        keyword=args.keyword,
        cps_config=app_config["CPS"],
        spike_config=app_config["SPIKE_DETECTION"],
    )

    output = {
        "spikes": [
            {
                "start_time": spike["start_time"],
                "peak_time": spike["peak_time"],
                "peak_value": spike["peak_value"],
                "jump_url": build_jump_url(args.url, spike["start_time"]),
            }
            for spike in result["spikes"]
        ]
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
