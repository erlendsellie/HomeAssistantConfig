"""Support for weather service."""
import asyncio
import logging
import re
from datetime import datetime, timedelta
import pandas as pd

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.components.sensor import ENTITY_ID_FORMAT, PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME,
    CONF_URL,
    DEVICE_CLASS_TIMESTAMP,
    HTTP_BAD_REQUEST,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify

_LOGGER = logging.getLogger(__name__)

ATTR_DISTANCE = "distance"
ATTR_PROPERTIES = "properties"
ATTR_LAST_UPDATE = "last_update"

CONF_TRACK_ID = "track_id"

ICON = 'mdi:ski'

DEFAULT_NAME = "skisporet"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        # vol.Optional(CONF_URL): cv.string,
        vol.Required(CONF_TRACK_ID): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Skisporet sensor."""
    name = config.get(CONF_NAME)
    # url = config.get(CONF_URL)
    track_id = config.get(CONF_TRACK_ID)
    # if url and not trackid:
    #     trackid=url.split("/")[5]

    _LOGGER.info(f"Setting up skisporet-sensor for {name}")
    dev = SkisporetSensor(hass, name, track_id)
    async_add_entities([dev], True)


class SkisporetSensor(Entity):
    """A sensor for a track"""
    def __init__(self, hass, name, track_id):
        """Initialize the sensor."""
        self._name = name
        self._track_id = track_id
        self._state = None
        self._distance = None
        self._properties = None
        self._last_update = None
        self.hass = hass
        self.entity_slug = "Skisporet {}".format(self._name)
        self.entity_id = ENTITY_ID_FORMAT.format(
            slugify(self.entity_slug.replace(' ', '_')))
        _LOGGER.info(f"Added skisporet-sensor {self.entity_id}")

    @property
    def unique_id(self):
        return self.entity_slug.replace(' ', '_')

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the name of the sensor."""
        return ICON
    @property
    def state(self):
        """Return the state of the device."""
        if self._state:
            return self._state.astimezone().isoformat()
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
                ATTR_DISTANCE: self._distance,
                ATTR_PROPERTIES: self._properties,
                ATTR_LAST_UPDATE: self._last_update,
                CONF_TRACK_ID: self._track_id
                }


    @property
    def device_class(self):
        """Return the device class of this entity, if any."""
        return DEVICE_CLASS_TIMESTAMP


    async def async_update(self):
        """Fetch status from skisporet."""
        _LOGGER.debug(f"Updating skisporet-sensor for {self._name}")

        tailSessionId = None
        url = 'https://skisporet.no/map/client/trackstatusstandalonedraw:standaloneStatusForLines'
        headers = {
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        data = { 
            'trackTypeKey': 'ts2sWithStatuses',
            'ids': f'[{self._track_id}]'
        }
        websession = async_get_clientsession(self.hass)

        try:
            with async_timeout.timeout(10):
                resp = await websession.post(url, headers=headers, data=data)
            tracks = await resp.json()
        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.error(f"No data from skisporet: {err}")
            return
        except Exception as err:
            _LOGGER.error(err)
            return

        statuses = tracks[0]['statuses']
        mintime = datetime(year=1960, month=1, day=1)
        for status in statuses:
            stattime = datetime.strptime(status['startTime'], '%Y-%m-%d %H:%M:%S.%f')
            if stattime > mintime:
                mintime = stattime
                tailSessionId = status['tailSessionId']
    
        if not tailSessionId:
            return
        d = int(datetime.now().strftime('%s')) * 1000
        url = f"https://skisporet.no/trackstatus/trackstatuspopup:StatusWithRouteInTabsHtml/{self._track_id}/{d}/{tailSessionId}/60/10"
        headers = {
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        data = {
            't:zoneid': f'TmpId_{d}' 
        }
    
        try:
            with async_timeout.timeout(10):
                resp = await websession.post(url, headers=headers, data=data)
            skisporet = await resp.json()
        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.error(f"No data from skisporet: {err}")
            return
        except Exception as err:
            _LOGGER.error(err)
            return
    
        parsed = pd.read_html(skisporet['_tapestry']['content'][0][1])
    
        i=0
        o = {}
        while i < len(parsed[0][0]):
            key = str(parsed[0][0][i]).replace(":", "").strip()
            val = str(parsed[0][1][i]).replace("Smøretips", "").strip()
            _LOGGER.debug(f"{key}: {val}")
            if key == "Oppdatert":
                self._last_update = val
                self._state = self._parse_timestamp(val)
            if key == "Lengde":
                self._distance = val
            if key == "Egenskaper":
                self._properties = val
            i = i + 1
    
    def _parse_timestamp(self, ts):
        _LOGGER.debug(f"Timestamp in: {ts}")
        days = 0
        hours = 0
        minutes = 0
        parts = ts.split(" og ")
    
    
        for part in parts:
            if "uke" in part:
                part = int(re.sub('\D', '', part))
                days = days + (part * 7)
                precision = '0'
            elif 'dag' in part:
                part = int(re.sub('\D', '', part))
                days = days + part
                precision = 'D'
            elif 'time' in part:
                part = int(re.sub('\D', '', part))
                hours = hours + part
                precision = 'T'
            elif 'minutt' in part:
                part = int(re.sub('\D', '', part))
                minutes = minutes + part
                precision = 'M'
    
        dt = datetime.now() - timedelta(days=days, hours=hours, minutes=minutes)
        if precision == '0':
            last = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        if precision == 'D':
            last = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        if precision == 'T':
            last = dt.replace(minute=0, second=0, microsecond=0)
        if precision == 'M':
            last = dt.replace(second=0, microsecond=0)
        _LOGGER.debug(f"Precision: {precision} - Timestamp out: {last}")
        return last




