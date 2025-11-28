#pragma once
#include "esphome/components/esp32_ble_tracker/esp32_ble_tracker.h"

// Parse Ingics iBS sensor temperature from BLE manufacturer data
// Supports both external probe sensors (temp at bytes 8-9) and
// built-in sensors (temp at bytes 11-12)
inline optional<float> parse_ingics_temp(const esphome::esp32_ble_tracker::ESPBTDevice &dev) {
  auto md = dev.get_manufacturer_datas();
  if (md.empty()) return {};
  auto &data = md[0].data;
  if (data.size() < 13) return {};

  // Check sensor subtype byte to determine temp location
  // 0x83 = built-in temp sensor (iBS01T, iBS03T, etc) - temp at bytes 11-12 (little-endian)
  // 0x85 = external probe sensor (iBS03TP, etc) - temp at bytes 8-9 (big-endian)
  uint8_t subtype = data[0];
  int16_t raw;
  
  if (subtype == 0x85) {
    // External probe: big-endian at bytes 8-9
    raw = (data[8] << 8) | data[9];
  } else {
    // Built-in sensor: little-endian at bytes 11-12
    raw = (data[12] << 8) | data[11];
  }
  
  return raw / 100.0f;
}
