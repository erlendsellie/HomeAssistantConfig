"""Platform for sensor integration."""
from datetime import timedelta, datetime as date
import logging

import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import ATTR_ATTRIBUTION
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
from homeassistant.util.dt import now

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Data provided by https://trv.no"

SCAN_INTERVAL = timedelta(hours=5)

CONF_BIN_NUMBER = "bin_number"
CONF_BIN_TYPE = "bin_type"
CONF_PICKUP_DAY = "pickup_day"

URL = "https://trv.no/wp-json/wasteplan/v1/calendar/"

# Default | Today | Tomorrow | This week | Emptied | Next Week
SENSOR_TYPES = {
    "Restavfall":      ["mdi:recycle",     "mdi:delete-alert", "mdi:delete-alert-outline", "mdi:delete-clock-outline", "mdi:delete-empty-outline", "mdi:delete-restore"],
    "Papir":           ["mdi:file",        "mdi:delete-alert", "mdi:delete-alert-outline", "mdi:delete-clock-outline", "mdi:delete-empty-outline", "mdi:delete-restore"],
    "Plastemballasje": ["mdi:bottle-soda", "mdi:delete-alert", "mdi:delete-alert-outline", "mdi:delete-clock-outline", "mdi:delete-empty-outline", "mdi:delete-restore"],
    "Hageavfall":      ["mdi:apple",       "mdi:delete-alert", "mdi:delete-alert-outline", "mdi:delete-clock-outline", "mdi:delete-empty-outline", "mdi:delete-restore"],
    "Tømmefri uke":    ["mdi:delete-forever-outline", "mdi:delete-forever-outline", "mdi:delete-forever-outline", "mdi:delete-forever-outline", "mdi:delete-forever-outline"],
    "Farlig avfall":   ["mdi:skull-crossbones", "mdi:skull-scan", "mdi:skull-scan-outline", "mdi:skull-scan-outline", "mdi:skull-outline", "mdi:skull-crossbones-outline"]
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_BIN_NUMBER): cv.string,
    vol.Optional(CONF_BIN_TYPE): vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Optional(CONF_PICKUP_DAY): cv.string
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the TRV sensor."""
    bin_number = config.get(CONF_BIN_NUMBER)
    pickup_day = 0
    if config.get(CONF_PICKUP_DAY):
        pickup_day = int(config.get(CONF_PICKUP_DAY))
    data = TRVData(bin_number)
    data.update()

    sensors = []
    for bintype in SENSOR_TYPES:
        sensors.append(TRVSensor(bintype, data, pickup_day))

    add_entities(sensors, True)


class TRVData:
    """Get the latest data for all authorities."""

    def __init__(self, bin_number):
        """Initialize the object."""
        self.data = None
        self.bin_number = bin_number

    # Update only once in scan interval.
    @Throttle(SCAN_INTERVAL)
    def update(self):
        """Get the latest data from TRV."""
        response = requests.get(URL + self.bin_number, timeout=10)
        if response.status_code != 200:
            _LOGGER.warning("Invalid response from TRV API")
        else:
            self.data = response.json()


class TRVSensor(Entity):
    """Single authority wasteplan sensor."""

    def __init__(self, name, data, pickup_day):
        """Initialize the sensor."""
        self._data = data
        self._name = name
        self._icon = SENSOR_TYPES[self._name][0]
        self._next_pickup_week = None
        self._date_week_start = None
        self._date_week_end = None
        self._description = None
        self._pickup_day = pickup_day
        self._state = None
        self.attrs = {ATTR_ATTRIBUTION: ATTRIBUTION}

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Return the icon."""
        return self._icon

    @property
    def device_state_attributes(self):
        """Return other details about the sensor state."""
        self.attrs["next_pickup_week"] = self._next_pickup_week
        self.attrs["description"] = self._description
        self.attrs["date_week_start"] = self._date_week_start
        self.attrs["date_week_end"] = self._date_week_end

        return self.attrs

    def update(self):
        """Update the sensor."""
        self._data.update()
        self._state = 'Ikke bestemt'

        today = date.now().weekday()
        tomorrow = (date.now() + timedelta(1)).weekday()
        weeks_until = 0
        this_week = now().isocalendar()[1]

        for entry in self._data.data['calendar']:
            if self._name == entry['wastetype']:

                descriptions = entry['description']
                if len(descriptions) > 0:
                    self._description = descriptions[self._name]['no']

                weeks_until = entry['week'] - this_week
                if 0 == weeks_until:

                    if today == self._pickup_day:
                        self._state = 'I dag'
                        self._icon = SENSOR_TYPES[self._name][1]
                    elif tomorrow == self._pickup_day:
                        self._state = 'I morgen'
                        self._icon = SENSOR_TYPES[self._name][2]
                    elif today < self._pickup_day:
                        self._state = 'Denne uken'
                        self._icon = SENSOR_TYPES[self._name][3]
                    else:
                        self._state = 'Tømt'
                        self._icon = SENSOR_TYPES[self._name][4]

                elif 1 == weeks_until:

                    self._state = 'Neste uke'
                    self._icon = SENSOR_TYPES[self._name][5]

                else:

                    self._state = 'Om '+str(weeks_until)+' uker'

                self._next_pickup_week = entry['week']
                self._date_week_start = entry['date_week_start']
                self._date_week_end = entry['date_week_end']
                break