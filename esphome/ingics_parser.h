#pragma once
#include "esphome/components/esp32_ble_tracker/esp32_ble_tracker.h"

// iBS03T/iBS03TP sensor data structure
struct IngicsIBS03TP {
  float internal;     // Internal sensor (bytes 5-6)
  float probe;        // Probe sensor (bytes 7-8)
  bool has_probe;     // True if probe value is valid (not 0x7FFF)
};

// Parse Ingics iBS03T/iBS03TP sensor from BLE manufacturer data
// Data format: 83 BC xx xx xx IL IH PL PH xx xx xx xx xx xx
//   - Bytes 5-6: Internal temp (little-endian, signed int16, /100 for °C)
//   - Bytes 7-8: Probe temp (little-endian, signed int16, /100 for °C), 0x7FFF if no probe
inline optional<IngicsIBS03TP> parse_ingics_ibs03tp(const esphome::esp32_ble_tracker::ESPBTDevice &dev, const char* sensor_name = "unknown") {
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

  // Debug: dump raw bytes
  char hex_buf[64];
  int pos = 0;
  for (size_t i = 0; i < data.size() && pos < 60; i++) {
    pos += snprintf(hex_buf + pos, sizeof(hex_buf) - pos, "%02X ", data[i]);
  }
  ESP_LOGD("ingics", "[%s] Raw data (%d bytes): %s", sensor_name, data.size(), hex_buf);

  IngicsIBS03TP result;
  
  // Internal temp (bytes 5-6, little-endian signed)
  int16_t internal_raw = (int16_t)((data[6] << 8) | data[5]);
  result.internal = internal_raw / 100.0f;
  
  // Probe temp (bytes 7-8, little-endian signed)
  int16_t probe_raw = (int16_t)((data[8] << 8) | data[7]);
  result.probe = probe_raw / 100.0f;
  result.has_probe = (probe_raw != 0x7FFF);  // 0x7FFF indicates no probe connected
  
  ESP_LOGD("ingics", "[%s] iBS03TP Internal=%.2f°C, Probe=%.2f°C (has_probe=%d)", 
           sensor_name, result.internal, result.probe, result.has_probe);
  
  return result;
}

// Parse Ingics iBS01T/iBS01G sensor from BLE manufacturer data
// Data format: 83 BC xx xx xx xx xx xx xx xx xx TL TH xx xx
// Temperature is at bytes 11-12 (little-endian signed int16, /100 for °C)
inline optional<float> parse_ingics_ibs01_temp(const esphome::esp32_ble_tracker::ESPBTDevice &dev, const char* sensor_name = "unknown") {
  auto md = dev.get_manufacturer_datas();
  
  if (md.empty()) {
    return {};
  }
  
  auto &data = md[0].data;
  
  if (data.size() < 13) {
    ESP_LOGW("ingics", "[%s] iBS01 data too short: %d bytes", sensor_name, data.size());
    return {};
  }

  // Debug: dump raw bytes
  char hex_buf[64];
  int pos = 0;
  for (size_t i = 0; i < data.size() && pos < 60; i++) {
    pos += snprintf(hex_buf + pos, sizeof(hex_buf) - pos, "%02X ", data[i]);
  }
  ESP_LOGD("ingics", "[%s] iBS01 Raw (%d bytes): %s", sensor_name, data.size(), hex_buf);

  // Temperature at bytes 11-12 (little-endian signed)
  int16_t temp_raw = (int16_t)((data[12] << 8) | data[11]);
  float temp = temp_raw / 100.0f;
  
  ESP_LOGD("ingics", "[%s] iBS01 Temp=%.2f°C (raw=0x%04X)", sensor_name, temp, (uint16_t)temp_raw);
  
  return temp;
}
