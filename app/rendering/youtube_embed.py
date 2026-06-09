import json
import re
from html import escape, unescape
from typing import Any


def render_wordpress_youtube_embed(youtube_video: dict[str, Any]) -> str:
    watch_url = youtube_watch_url(youtube_video)
    if not watch_url:
        return ""

    block_attrs = {
        "url": watch_url,
        "type": "video",
        "providerNameSlug": "youtube",
        "responsive": True,
        "className": "wp-embed-aspect-16-9 wp-has-aspect-ratio",
    }
    block_json = json.dumps(block_attrs, separators=(",", ":"), ensure_ascii=False)
    safe_url = escape(watch_url)
    return (
        f"<!-- wp:embed {block_json} -->"
        '<figure class="wp-block-embed is-type-video is-provider-youtube wp-block-embed-youtube '
        'wp-embed-aspect-16-9 wp-has-aspect-ratio">'
        '<div class="wp-block-embed__wrapper">'
        f"\n{safe_url}\n"
        "</div>"
        "</figure>"
        "<!-- /wp:embed -->"
    )


def youtube_watch_url(youtube_video: dict[str, Any]) -> str:
    video_id = str(youtube_video.get("video_id") or "").strip()
    if not video_id:
        video_id = _video_id_from_url(str(youtube_video.get("url") or youtube_video.get("embed_url") or ""))
    if video_id:
        return f"https://www.youtube.com/watch?v={video_id}"

    url = str(youtube_video.get("url") or "").strip()
    if url.startswith(("https://www.youtube.com/", "https://youtu.be/")):
        return url
    return ""


def render_local_youtube_iframes(html: str) -> str:
    return re.sub(
        r"<!-- wp:embed (?P<attrs>\{.*?\}) -->\s*<figure\b.*?</figure>\s*<!-- /wp:embed -->",
        _local_iframe_replacement,
        html,
        flags=re.DOTALL,
    )


def _video_id_from_url(url: str) -> str:
    patterns = (
        r"youtube\.com/watch\?v=([A-Za-z0-9_-]{6,})",
        r"youtube\.com/embed/([A-Za-z0-9_-]{6,})",
        r"youtu\.be/([A-Za-z0-9_-]{6,})",
    )
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return ""


def _local_iframe_replacement(match: re.Match[str]) -> str:
    try:
        attrs = json.loads(unescape(match.group("attrs")))
    except json.JSONDecodeError:
        return match.group(0)

    if attrs.get("providerNameSlug") != "youtube":
        return match.group(0)
    video_id = _video_id_from_url(str(attrs.get("url") or ""))
    if not video_id:
        return match.group(0)

    embed_url = f"https://www.youtube.com/embed/{video_id}"
    return (
        f'<iframe src="{escape(embed_url)}" title="YouTube video" '
        'width="560" height="315" loading="lazy" '
        'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" '
        "allowfullscreen></iframe>"
    )
