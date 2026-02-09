#!/usr/bin/env python3
"""Play a sequence of TTS messages with delays between them.

Usage: tts_sequence.py [--delay SECS] [--script SCRIPT_NAME] [--lang LANG] "msg1" "msg2" "msg3"

Examples:
  tts_sequence.py --delay 10 "Joke 1" "Joke 2" "Joke 3"
  tts_sequence.py --delay 5 --lang nb-NO "Norsk vits 1" "Norsk vits 2"
  tts_sequence.py "Single message now"
"""
import argparse
import json
import time
import urllib.request

def _read_token():
    with open("/config/secrets.yaml") as f:
        for line in f:
            if line.startswith("ha_token:"):
                return line.split(":", 1)[1].strip().strip('"')
    raise RuntimeError("ha_token not found in /config/secrets.yaml")

TOKEN = _read_token()
HA_URL = "http://localhost:8123/api/services"


def call_service(domain, service, data):
    url = f"{HA_URL}/{domain}/{service}"
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status
    except Exception as e:
        print(f"Error: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Play TTS messages in sequence")
    parser.add_argument("messages", nargs="+", help="Messages to play")
    parser.add_argument("--delay", type=int, default=10, help="Seconds between messages (default: 10)")
    parser.add_argument("--script", default="playmessage", help="Script name to call (default: playmessage)")
    parser.add_argument("--lang", default=None, help="Language override (e.g. nb-NO, en-US)")
    args = parser.parse_args()

    for i, message in enumerate(args.messages):
        data = {"entity_id": f"script.{args.script}", "message": message}
        if args.lang:
            data["language"] = args.lang
        print(f"[{i+1}/{len(args.messages)}] Playing: {message[:60]}...")
        call_service("script", args.script, data)
        if i < len(args.messages) - 1:
            time.sleep(args.delay)

    print("Done.")


if __name__ == "__main__":
    main()
