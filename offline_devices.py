import json
import time

db_path = "/config/zigbee2mqtt/database.db"
reg_path = "/config/.storage/core.device_registry"

with open(db_path, "r") as f:
    devices = []
    for line in f:
        if line.strip():
            try:
                device = json.loads(line)
                if device.get("type") in ["Router", "EndDevice"]:
                    devices.append(device)
            except:
                pass

with open(reg_path, "r") as f:
    reg_data = json.load(f)

# Build a map of ieeeAddr to HA names
ieee_to_ha_name = {}
for dev in reg_data["data"]["devices"]:
    for ident in dev.get("identifiers", []):
        if len(ident) == 2 and ident[0] == "mqtt" and ident[1].startswith("zigbee2mqtt_"):
            ieee = ident[1].replace("zigbee2mqtt_", "")
            ieee_to_ha_name[ieee] = dev.get("name", "Unknown")

now = time.time() * 1000
offline_24h = [d for d in devices if d.get("lastSeen") and (now - d.get("lastSeen", now)) > 24*3600*1000]

print(f"Total Offline Devices (>24h): {len(offline_24h)}\n")
for d in offline_24h:
    ieee = d.get('ieeeAddr')
    ha_name = ieee_to_ha_name.get(ieee, "Not found in HA")
    print(f"HA Name: {ha_name}")
    print(f"  ieeeAddr: {ieee}")
    print(f"  Model: {d.get('modelId')}")
    print(f"  Manufacturer: {d.get('manufName')}")
    last_seen_hours = (now - d.get('lastSeen', now)) / 1000 / 3600
    print(f"  Offline for: {last_seen_hours:.1f} hours\n")
