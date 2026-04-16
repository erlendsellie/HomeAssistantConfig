#!/usr/bin/env python3
import json
from datetime import datetime
import os

EXTENDED_FILE = "/config/.storage/inatur_trondelag_extended.json"

def main():
    try:
        with open(EXTENDED_FILE, "r", encoding="utf-8") as f:
            extended_data = json.load(f)
    except Exception:
        extended_data = {}

    expiring_soon = []
    now = datetime.now()

    for oid, offer in extended_data.items():
        soknadsfrist_ms = offer.get("soknadsfrist_ms")
        if not soknadsfrist_ms:
            continue

        dt = datetime.fromtimestamp(soknadsfrist_ms / 1000.0)
        days_diff = (dt.date() - now.date()).days

        # If it expires today (0) or tomorrow (1)
        if 0 <= days_diff <= 1:
            expiring_soon.append({
                "tittel": offer.get("tittel"),
                "url": offer.get("url"),
                "kommuner": offer.get("kommuner") or "Ukjent",
                "soknadsfrist_iso": offer.get("soknadsfrist_iso"),
                "days_until_expiry": days_diff,
                "harTrekning": offer.get("harTrekning", False),
                "kortBeskrivelse": offer.get("kortBeskrivelse", ""),
                "ai_summary": offer.get("ai_summary") or offer.get("kortBeskrivelse", "")
            })

    output = {
        "count": len(expiring_soon),
        "expiring": expiring_soon
    }
    print(json.dumps(output, ensure_ascii=False))

if __name__ == "__main__":
    main()
