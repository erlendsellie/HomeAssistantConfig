#!/usr/bin/env python3
import json
import urllib.request
import urllib.parse
from datetime import datetime
import time
import os
import re

try:
    import yaml
except ImportError:
    pass

STORAGE_FILE = "/config/.storage/inatur_trondelag_seen.json"
EXTENDED_FILE = "/config/.storage/inatur_trondelag_extended.json"
SECRETS_FILE = "/config/secrets.yaml"
BLACKLIST = ["Grong", "Lierne", "Namdalseid", "Namsos", "Namsskogan", "Nærøysund", "Røyrvik", "Rosse", "Snåsa"]

def get_gemini_key():
    try:
        with open(SECRETS_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
            # Simple fallback parsing if pyyaml is somehow not available
            if 'yaml' in globals():
                secrets = yaml.safe_load(content)
                return secrets.get('gemini_api_key')
            else:
                for line in content.split('\n'):
                    if line.startswith('gemini_api_key:'):
                        return line.split(':', 1)[1].strip()
    except Exception:
        pass
    return None

def strip_html(html):
    html = re.sub(r'<script.*?</script>', '', html, flags=re.DOTALL)
    html = re.sub(r'<style.*?</style>', '', html, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', html)
    return re.sub(r'\s+', ' ', text).strip()

def fetch_offer_text(url_path):
    try:
        url = "https://www.inatur.no" + url_path
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                html = response.read().decode('utf-8')
                return strip_html(html)
    except Exception:
        pass
    return ""

def fetch_all_pages():
    search_filter = '[{"felt":"arter","sokeord":"lirype"},{"felt":"fylker","sokeord":"Trøndelag"},{"felt":"type","sokeord":"smaavilttilbud"}]'
    encoded_filter = urllib.parse.quote(search_filter)
    base_url = "https://www.inatur.no/internal/search"

    all_offers = []
    page = 0
    total_pages = 1

    while page < total_pages:
        url = f"{base_url}?f={encoded_filter}&ledig=true&p={page}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        try:
            with urllib.request.urlopen(req) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    if page == 0:
                        total_pages = data.get('paginering', {}).get('totaltAntallSider', 1)
                    all_offers.extend(data.get('resultat', []))
                else:
                    break
        except Exception:
            break
        page += 1
        time.sleep(0.5)
    return all_offers

def generate_ai_summary(new_offers_text, api_key):
    if not api_key:
        return ""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    prompt = f"Her er et eller flere jakt/fisketilbud publisert på inatur.no. Gi et kort, engasjerende sammendrag (max 2-3 setninger) på norsk om hva dette er generelt. Trekk spesifikt ut informasjon om terrenget (f.eks. om det er et fjellområde), om hytte er inkludert, og hvor mange kort eller plasser som er tilgjengelige, dersom det er nevnt. Vær informativ men veldig kortfattet:\n\n{new_offers_text}"

    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                candidates = data.get("candidates", [])
                if candidates:
                    return candidates[0]["content"]["parts"][0]["text"].strip()
    except Exception:
        pass
    return ""

def main():
    try:
        with open(STORAGE_FILE, "r", encoding="utf-8") as f:
            seen_data = json.load(f)
            seen_offers = seen_data.get("offers", {})
    except Exception:
        seen_offers = {}

    api_offers = fetch_all_pages()

    filtered_offers = []
    for o in api_offers:
        komm = o.get('kommuner', [])
        komm_str = " ".join(komm).lower() if komm else ""
        if any(b.lower() in komm_str for b in BLACKLIST):
            continue
        if "innenbygds" in o.get('tittel', '').lower():
            continue
        filtered_offers.append(o)

    new_or_updated = []
    current_offers = {}

    # Load previous extended data so we can preserve stored ai_summary values
    try:
        with open(EXTENDED_FILE, "r", encoding="utf-8") as f:
            extended_data = json.load(f)
    except Exception:
        extended_data = {}

    now = datetime.now()

    for offer in filtered_offers:
        oid = offer.get("id")
        updated = offer.get("sistOppdatert") or 0
        published = offer.get("sistPublisert") or 0
        updated_sec = updated / 1000.0 if updated > 2000000000 else updated
        published_sec = published / 1000.0 if published > 2000000000 else published
        latest = max(updated_sec, published_sec)

        tittel = offer.get("tittel")

        soknadsfrist_ms = offer.get("soknadsfrist")
        soknadsfrist_str = None
        days_until_expiry = None
        time_left_sec = None
        if soknadsfrist_ms:
            dt = datetime.fromtimestamp(soknadsfrist_ms / 1000.0)
            soknadsfrist_str = dt.isoformat()
            time_left = dt - now
            days_until_expiry = time_left.days
            time_left_sec = time_left.total_seconds()

        komm = offer.get("kommuner")

        extended = {
            "tittel": tittel,
            "url": offer.get("url"),
            "kommuner": offer.get("kommunerFormatert") or komm,
            "tilbydernavn": offer.get("tilbydernavn"),
            "sistOppdatertFormatert": offer.get("sistOppdatertFormatert"),
            "soknadsfrist_ms": soknadsfrist_ms,
            "soknadsfrist_iso": soknadsfrist_str,
            "days_until_expiry": days_until_expiry,
            "harTrekning": offer.get("harTrekning"),
            "kortBeskrivelse": offer.get("kortBeskrivelse")
        }
        extended_data[oid] = extended

        prev_update = seen_offers.get(oid, {}).get("last_update", 0)

        current_offers[oid] = {
            "last_update": latest,
            "tittel": tittel
        }

        is_new = oid not in seen_offers
        is_updated = latest > prev_update and not is_new

        if is_new or is_updated:
            item = extended.copy()
            item["id"] = oid
            item["is_new"] = is_new
            item["is_updated"] = is_updated
            new_or_updated.append(item)

    ai_key = get_gemini_key()
    batch_summaries = []
    for item in new_or_updated:
        oid = item["id"]
        # Reuse stored summary if already present in extended database
        if extended_data.get(oid, {}).get("ai_summary"):
            item["ai_summary"] = extended_data[oid]["ai_summary"]
            batch_summaries.append(item["ai_summary"])
            continue
        # Generate a new per-offer summary
        try:
            full_text = fetch_offer_text(item.get("url", ""))
            kort = full_text if full_text else item.get("kortBeskrivelse", "")
            kort_trunc = kort[:15000]
            offer_text = f"TILBUD: {item['tittel']}\nFRIST: {item['soknadsfrist_iso']}\nINFORMASJON FRA NETTSIDEN:\n{kort_trunc}"
            summary = generate_ai_summary(offer_text, ai_key)
        except Exception:
            summary = ""
        item["ai_summary"] = summary
        extended_data[oid]["ai_summary"] = summary
        if summary:
            batch_summaries.append(summary)

    ai_summary = "\n\n".join(batch_summaries)

    with open(EXTENDED_FILE, "w", encoding="utf-8") as f:
        json.dump(extended_data, f, indent=2, ensure_ascii=False)

    # Copy to www folder for the browser dashboard
    www_data = "/config/www/inatur/data.json"
    try:
        os.makedirs(os.path.dirname(www_data), exist_ok=True)
        with open(www_data, "w", encoding="utf-8") as f:
            json.dump(extended_data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

    with open(STORAGE_FILE, "w", encoding="utf-8") as f:
        json.dump({"offers": current_offers, "last_check": datetime.now().isoformat()}, f, ensure_ascii=False)

    output = {
        "new_or_updated": new_or_updated,
        "ai_summary": ai_summary,
        "total_filtered": len(filtered_offers),
        "new_count": len([x for x in new_or_updated if x.get("is_new")]),
        "last_check": datetime.now().isoformat()
    }

    print(json.dumps(output, ensure_ascii=False))

if __name__ == "__main__":
    main()
