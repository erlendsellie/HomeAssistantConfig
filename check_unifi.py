import json
import ssl
import urllib.request
import urllib.error
from pathlib import Path

# Ignore SSL warnings for local self-signed certs
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

url = 'https://192.168.1.1'
SECRETS_FILE = Path("/config/secrets.yaml")


def load_secret(key):
    try:
        for line in SECRETS_FILE.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if ":" not in stripped:
                continue
            found_key, value = stripped.split(":", 1)
            if found_key.strip() == key:
                return value.strip().strip("'\"")
    except FileNotFoundError:
        return None
    return None


username = load_secret("unifi_username")
password = load_secret("unifi_password")

if not username or not password:
    raise SystemExit("Missing unifi_username/unifi_password in /config/secrets.yaml")

def request(method, path, data=None, headers=None):
    if headers is None:
        headers = {}
    if data is not None:
        data = json.dumps(data).encode('utf-8')
        headers['Content-Type'] = 'application/json'

    req = urllib.request.Request(f"{url}{path}", data=data, headers=headers, method=method)
    try:
        response = urllib.request.urlopen(req, context=ctx)
        return response, json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code} for {path}")
        print(e.read().decode('utf-8'))
        return None, None

# 1. Login
headers = {}
login_data = {
    'username': username,
    'password': password,
    'remember': True
}

# Try older API controller login
response, login_resp = request('POST', '/api/login', data=login_data)

if not response:
    # Try newer UniFi OS login
    response, login_resp = request('POST', '/api/auth/login', data=login_data)

if not response:
    print("Failed to login to UniFi Controller")
    exit(1)

cookie = response.getheader('Set-Cookie')
# Some controllers return multiple Set-Cookie headers; we'll grab the first, or concatenate
if cookie:
    headers['Cookie'] = cookie

# Try different API paths for devices
paths_to_try = [
    '/api/s/default/stat/device',
    '/proxy/network/api/s/default/stat/device'
]

devices_resp = None
for p in paths_to_try:
    _, devices_resp = request('GET', p, headers=headers)
    if devices_resp and devices_resp.get('data'):
        break

if not devices_resp or not devices_resp.get('data'):
    print("No devices found or wrong site.")
    exit(1)

data = devices_resp.get('data', [])
for device in data:
    if device.get('type') == 'uap':
        name = device.get('name', device.get('mac'))
        print(f"Access Point: {name}")

        radio_table = device.get('radio_table', [])
        for radio in radio_table:
            band = "2.4GHz" if radio.get('radio') == 'ng' else ("5GHz" if radio.get('radio') == 'na' else "6GHz")
            channel = radio.get('channel')
            tx_power = radio.get('tx_power')
            ht = radio.get('ht')
            print(f"  - {band} (Radio {radio.get('radio')}): Channel {channel}, HT{ht}, TX Power {tx_power}")

        print("---")
