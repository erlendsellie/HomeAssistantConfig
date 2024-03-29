#legg denne fila under /packages.
#Bytt ut sensor.varmepumpe_watt med din sensor for strømforbruk for varmepumpe
#Bytt ut climate.varmepumpe med din enhet for varmepumpe.
#Bytt ut switch.drypppanne med din enhet for å slå av og på drypppanne (eller bytt navn på eksisterende enhet)

#Det blir opprettet en ny hjelper, kalt input_number.drypppanne_forsinkelse,
#hvor du kan sette forsinkelsen for hvor lenge drypppannen skal være på etter avising er ferdig.
#Denne er default 30.

template:
  - binary_sensor:
      - name: "Varmepumpe Aviser"
        unique_id: d1f76661-158a-4aa6-916b-0a3a1f02bf1d
        state: >-
          {%set kjorer_avising = 
              states('climate.varmepumpe') != 'off' 
              and states('sensor.varmepumpe_watt') | float(default=600) < 100
              %}
          {{kjorer_avising}}
input_number:
  drypppanne_forsinkelse:
    name: Behold Drypppanne av etter avising
    min: 0
    max: 120
    step: 1
    initial: 30
    mode: slider
    unit_of_measurement: "minutes"

automation:
  - id: f7e3edd4-f0e7-4338-bdc4-e4ae068b52b0
    alias: Slå på drypppanne
    trigger:
      - platform: state
        entity_id: binary_sensor.varmepumpe_aviser
        to: "on"
    action:
      - alias: Start varme
        service: switch.turn_on
        target:
          entity_id: switch.drypppanne
      - alias: Vent til varmepumpe ikke aviser seg lengre
        wait_for_trigger:
          platform: state
          entity_id: binary_sensor.varmepumpe_aviser
          to: "off"
      - alias: Vent I antall gitte minutter min
        delay:
          minutes: "{{states('input_number.drypppanne_forsinkelse') | float(default=20)}}"
      - alias: Slå av varme
        service: switch.turn_off
        target:
          entity_id: switch.drypppanne
