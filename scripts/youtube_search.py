#!/usr/bin/env python3
"""Search YouTube and return video results as JSON."""
import sys
import json
import urllib.request
import urllib.parse
import re


def search(query, max_results=5):
    search_url = (
        "https://www.youtube.com/results?search_query="
        + urllib.parse.quote(query)
    )
    req = urllib.request.Request(
        search_url,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        html = resp.read().decode("utf-8")

    # Try structured data first
    match = re.search(r"var ytInitialData = ({.*?});</script>", html)
    if not match:
        # Fallback: extract video IDs from HTML
        video_ids = re.findall(r"watch\?v=([a-zA-Z0-9_-]{11})", html)
        seen = []
        for vid in video_ids:
            if vid not in seen:
                seen.append(vid)
            if len(seen) >= max_results:
                break
        if seen:
            return {
                "results": [
                    {"video_id": v, "url": f"https://www.youtube.com/watch?v={v}"}
                    for v in seen
                ],
                "count": len(seen),
            }
        return {"error": "Could not parse YouTube results"}

    data = json.loads(match.group(1))
    results = []
    try:
        contents = (
            data["contents"]["twoColumnSearchResultsRenderer"]
            ["primaryContents"]["sectionListRenderer"]["contents"]
        )
        for section in contents:
            items = section.get("itemSectionRenderer", {}).get("contents", [])
            for item in items:
                if "videoRenderer" in item:
                    video = item["videoRenderer"]
                    video_id = video["videoId"]
                    title = video.get("title", {}).get("runs", [{}])[0].get("text", "")
                    length = video.get("lengthText", {}).get("simpleText", "")
                    results.append({
                        "title": title,
                        "video_id": video_id,
                        "url": f"https://www.youtube.com/watch?v={video_id}",
                        "duration": length,
                    })
                    if len(results) >= max_results:
                        break
            if len(results) >= max_results:
                break
    except (KeyError, IndexError):
        pass

    if not results:
        return {"error": "No video results found"}

    return {"results": results, "count": len(results)}


if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else ""
    max_r = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    if not query:
        print(json.dumps({"error": "No search query provided"}))
        sys.exit(1)
    print(json.dumps(search(query, max_r)))
