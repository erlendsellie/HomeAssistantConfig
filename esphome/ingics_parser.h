#pragma once
#include "esphome/components/esp32_ble_tracker/esp32_ble_tracker.h"

// Ingics iBS03T/iBS03TP sensor temperature data
struct IngicsTemp {
  float internal;     // Internal sensor (bytes 5-6)
  float probe;        // Probe sensor (bytes 7-8)
  bool has_probe;     // True if probe value is valid (not 0x7FFF)
};

// Parse Ingics iBS sensor temperature from BLE manufacturer data
// iBS03T/iBS03TP sensors:
//   - Bytes 5-6: Internal temp (little-endian, signed int16, /100 for °C)
//   - Bytes 7-8: Probe temp (little-endian, signed int16, /100 for °C), 0x7FFF if no probe

inline optional<IngicsTemp> parse_ingics_temp_full(const esphome::esp32_ble_tracker::ESPBTDevice &dev, const char* sensor_name = "unknown") {
  auto md = dev.get_manufacturer_datas();
  
  if (md.empty()) {
    ESP_LOGD("ingics", "[%s] No manufacturer data", sensor_name);
    return {};
  }
  
  auto &data = md[0].data;
  
  if (data.size() < 9) {
    ESP_LOGW("ingics", "[%s] Data too short: %d bytes", sensor_name, data.size());
    return {};
  }

  IngicsTemp result;
  
  // Internal temp (bytes 5-6, little-endian signed)
  int16_t internal_raw = (int16_t)((data[6] << 8) | data[5]);
  result.internal = internal_raw / 100.0f;
  
  // Probe temp (bytes 7-8, little-endian signed)
  int16_t probe_raw = (int16_t)((data[8] << 8) | data[7]);
  result.probe = probe_raw / 100.0f;
  result.has_probe = (probe_raw != 0x7FFF);  // 0x7FFF indicates no probe connected
  
  ESP_LOGD("ingics", "[%s] Internal=%.2f°C, Probe=%.2f°C (has_probe=%d)", 
           sensor_name, result.internal, result.probe, result.has_probe);
  
  return result;
}

// Simple wrapper returning just internal temp (for sensors without probe)
inline optional<float> parse_ingics_temp(const esphome::esp32_ble_tracker::ESPBTDevice &dev, const char* sensor_name = "unknown") {
  auto result = parse_ingics_temp_full(dev, sensor_name);
  if (!result) return {};
  return result->internal;
}
