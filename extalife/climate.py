import logging
from pprint import pformat
from .pyextalife import ExtaLifeAPI

# from homeassistant.components.extalife import ExtaLifeChannel
from . import ExtaLifeChannel
from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    HVAC_MODE_AUTO,
    HVAC_MODE_HEAT,
    SUPPORT_TARGET_TEMPERATURE,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_HEAT,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS

_LOGGER = logging.getLogger(__name__)


# Exta Life logic - TBC
# set temp: set state to 1. Controller returns state = 0. State = 0 means work_mode should be set to false
# set auto: set state to 0. Controller returns state = 1. State = 1 means work_mode should be set to true

# map Exta Life "work_mode" field
EXTA_HVAC_MODE = {
    True: HVAC_MODE_AUTO,
    False: HVAC_MODE_HEAT,
}

# map Exta Life notification "state" field
EXTA_STATE_HVAC_MODE = {
    1: HVAC_MODE_AUTO,
    0: HVAC_MODE_HEAT,
}

# map Exta Life "work_mode" field
HVAC_MODE_EXTA = {
    HVAC_MODE_AUTO: True,
    HVAC_MODE_HEAT: False
}

# map Exta Life "power" field
EXTA_HVAC_ACTION = {
    1: CURRENT_HVAC_HEAT,
    0: CURRENT_HVAC_IDLE
}

# map HA action to Exta Life "state" field
HVAC_ACTION_EXTA = {
    CURRENT_HVAC_HEAT: 1,
    CURRENT_HVAC_IDLE: 0
}

# map HA HVAC mode to Exta Life action
HA_MODE_ACTION = {
    HVAC_MODE_AUTO: ExtaLifeAPI.ACTN_SET_RGT_MODE_AUTO,
    HVAC_MODE_HEAT: ExtaLifeAPI.ACTN_SET_RGT_MODE_MANUAL
}

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up ExtaLife heat controllers."""
    if discovery_info is None:
        return

    _LOGGER.debug("Discovery: %s", pformat(discovery_info))

    add_entities([ExtaLifeClimate(device) for device in discovery_info])

class ExtaLifeClimate(ExtaLifeChannel, ClimateDevice):
    """Representation of Exta Life Thermostat."""

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE

    @property
    def max_temp(self):
        return 50

    @property
    def min_temp(self):
        return 5

    @property
    def target_temperature_step(self):
        return 0.5

    @property
    def precision(self):
        return 0.5

    @property
    def hvac_action(self):
        # for now there's no data source to show it. data.power does not reflect this information
        return None

    @property
    def hvac_mode(self):
        return EXTA_HVAC_MODE.get(self.channel_data.get("work_mode"))

    @property
    def hvac_modes(self):
        return [HVAC_MODE_AUTO, HVAC_MODE_HEAT]

    def set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode (heat, auto => manual, auto)."""
        if self.action(HA_MODE_ACTION.get(hvac_mode), value=self.channel_data.get("value")):
            self.channel_data["work_mode"] = HVAC_MODE_EXTA.get(hvac_mode)
            self.schedule_update_ha_state()

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return float(int(self.channel_data.get("temperature")) / 10.0)

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return float(self.channel_data.get("value") / 10.0)

    def set_temperature(self, **kwargs):
        """Set new target temperatures."""
        temperature = kwargs.get(ATTR_TEMPERATURE)

        if temperature is None:
            return
        temp_el = temperature * 10.0

        if self.action(ExtaLifeAPI.ACTN_SET_TMP, value=temp_el):
            self.channel_data["value"] = temp_el
            self.channel_data["work_mode"] = HVAC_MODE_EXTA[HVAC_MODE_HEAT]
            #self.channel_data["power"] = 1 if int(temp_el) > int(self.channel_data["value"]) else 0
            self.schedule_update_ha_state()

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        data = self.channel_data
        attrs = {"waiting_to_synchronize": data.get("waiting_to_synchronize"),
                "battery_status": data.get("battery_status"),
                "temperature_old": data.get("temperature_old")
        }

        return attrs

    def on_state_notification(self, data):
        """ React on state notification from controller """
        state = data.get("state")

        ch_data = self.channel_data.copy()
        #ch_data["power"] = 1 if state else 0
        ch_data["work_mode"] = EXTA_STATE_HVAC_MODE.get(state)
        ch_data["value"] = data.get("value")        # update set (target) temperature

        # update only if notification data contains new status; prevent HA event bus overloading
        if ch_data != self.channel_data:
            self.channel_data.update(ch_data)
            self.async_schedule_update_ha_state(True)
