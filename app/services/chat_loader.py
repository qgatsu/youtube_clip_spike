from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator, Optional

from chat_downloader import ChatDownloader, errors


@dataclass(frozen=True)
class ChatMessage:
    timestamp_seconds: float
    message: str
    is_member: bool


class ChatLoader:
    """Wrapper around ChatDownloader to keep the rest of the app decoupled."""

    def __init__(self, request_timeout: int = 10) -> None:
        self._timeout = request_timeout  # reserved for future use

    def fetch_messages(
        self,
        url: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        message_limit: Optional[int] = None,
    ) -> Iterable[ChatMessage]:
        downloader = ChatDownloader()
        options = {
            "start_time": start_time,
            "end_time": end_time,
            "message_limit": message_limit,
        }
        try:
            chat = downloader.get_chat(url, **{k: v for k, v in options.items() if v})
            return self._serialize(chat)
        except errors.ParsingError as exc:
            raise ValueError("チャット情報を解析できませんでした。URLを確認してください。") from exc
        except errors.ChatDownloaderError as exc:
            raise ValueError("チャットの取得に失敗しました。") from exc

    def _serialize(self, chat_iter: Iterator[dict]) -> Iterator[ChatMessage]:
        for message in chat_iter:
            timestamp = message.get("time_in_seconds")
            if timestamp is None:
                continue
            text = message.get("message", "")
            badges = message.get("author", {}).get("badges", [])
            is_member = bool(badges)
            yield ChatMessage(
                timestamp_seconds=float(timestamp),
                message=text,
                is_member=is_member,
            )
