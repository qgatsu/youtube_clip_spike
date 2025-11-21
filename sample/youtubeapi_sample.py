import os
import re
import requests
from urllib.parse import urlparse, parse_qs

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")  # 環境変数から読む想定


def extract_video_id(url: str) -> str | None:
    """
    YouTube URL から videoId を抽出する簡易関数。
    対応例:
      - https://www.youtube.com/watch?v=ABC123xyz
      - https://youtu.be/ABC123xyz
      - https://www.youtube.com/embed/ABC123xyz
      - すでに ID だけ渡された場合もそのまま返す
    """
    # すでにID（英数字 + _-）だけが渡されたっぽい場合
    if re.fullmatch(r"[0-9A-Za-z_-]{6,}", url):
        return url

    parsed = urlparse(url)

    # youtu.be 短縮URL
    if parsed.netloc in ("youtu.be", "www.youtu.be"):
        vid = parsed.path.lstrip("/")
        return vid or None

    # watch?v=xxx 形式
    if "youtube.com" in parsed.netloc:
        qs = parse_qs(parsed.query)
        if "v" in qs:
            return qs["v"][0]

        # /embed/VIDEO_ID 形式
        m = re.match(r"^/embed/([0-9A-Za-z_-]{6,})", parsed.path)
        if m:
            return m.group(1)

    return None


def search_candidate_videos_by_id(video_id: str, max_results: int = 50) -> list[dict]:
    """
    search.list で videoId をクエリにして候補動画を取得。
    ここでは概要欄に元URLが含まれているかまではまだ判定しない。
    """
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "key": YOUTUBE_API_KEY,
        "part": "snippet",
        "type": "video",
        "q": video_id,
        "maxResults": max_results,
    }
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    data = resp.json()
    return data.get("items", [])


def fetch_full_descriptions(video_ids: list[str]) -> dict[str, dict]:
    """
    videos.list でフルの概要欄などを取得。
    戻り値: {videoId: video_resource_dict}
    """
    if not video_ids:
        return {}

    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        "key": YOUTUBE_API_KEY,
        "part": "snippet,statistics,contentDetails",
        "id": ",".join(video_ids),
        "maxResults": len(video_ids),
    }
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    data = resp.json()
    result = {}
    for item in data.get("items", []):
        vid = item["id"]
        result[vid] = item
    return result


def find_clips_by_original_url(original_url: str, max_results: int = 50) -> list[dict]:
    """
    元動画URLから、そのURL（またはID）が概要欄に書かれている動画（切り抜き候補）を返す。
    戻り値の各dictには、title / channelTitle / url / description などを含める。
    """
    video_id = extract_video_id(original_url)
    if not video_id:
        raise ValueError(f"動画IDをURLから抽出できませんでした: {original_url}")

    # 1. search.list で候補検索
    search_items = search_candidate_videos_by_id(video_id, max_results=max_results)

    # 2. 候補の videoId をリストアップ
    candidate_ids = []
    for item in search_items:
        vid = item["id"].get("videoId")
        if vid:
            candidate_ids.append(vid)

    candidate_ids = list(dict.fromkeys(candidate_ids))  # 重複除去

    # 3. videos.list でフル概要欄取得
    video_map = fetch_full_descriptions(candidate_ids)

    # 4. 概要欄に元URL/IDが含まれているかチェック
    results = []
    patterns = [
        video_id,
        f"https://www.youtube.com/watch?v={video_id}",
        f"https://youtu.be/{video_id}",
    ]

    for vid in candidate_ids:
        item = video_map.get(vid)
        if not item:
            continue

        snippet = item.get("snippet", {})
        description = snippet.get("description", "") or ""
        # 判定: どれか1つでも含まれていればOKとする
        if any(p in description for p in patterns):
            results.append(
                {
                    "videoId": vid,
                    "title": snippet.get("title"),
                    "channelTitle": snippet.get("channelTitle"),
                    "description": description,
                    "url": f"https://www.youtube.com/watch?v={vid}",
                    "publishedAt": snippet.get("publishedAt"),
                    "statistics": item.get("statistics", {}),
                    "contentDetails": item.get("contentDetails", {}),
                }
            )

    return results


if __name__ == "__main__":
    # 例: 元動画URLを指定して実行
    original = "https://www.youtube.com/watch?v=ABC123xyz"
    clips = find_clips_by_original_url(original, max_results=50)

    print(f"Found {len(clips)} candidate clips:")
    for c in clips:
        print("--------------")
        print("Title:", c["title"])
        print("Channel:", c["channelTitle"])
        print("URL:", c["url"])
        # 必要なら description も print するが長いので省略可
        # print("Description:", c["description"])
