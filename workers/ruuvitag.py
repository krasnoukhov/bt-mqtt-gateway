from mqtt import MqttMessage, MqttConfigMessage
from workers.base import BaseWorker

import logger


REQUIREMENTS = ["ruuvitag_sensor"]

# Supports all attributes of Data Format 2, 3, 4 and 5 of the RuuviTag.
# See https://github.com/ruuvi/ruuvi-sensor-protocols for the sensor protocols.
ATTR_CONFIG = [
    # (attribute_name, device_class, unit_of_measurement)
    ("acceleration", "acceleration", "mG"),
    ("acceleration_x", "acceleration_x", "mG"),
    ("acceleration_y", "acceleration_y", "mG"),
    ("acceleration_z", "acceleration_z", "mG"),
    ("battery", "battery", "mV"),
    ("data_format", "data_format", ""),
    ("humidity", "humidity", "%"),
    ("identifier", "identifier", ""),
    ("mac", "mac", ""),
    ("measurement_sequence_number", "measurement_sequence_number", ""),
    ("movement_counter", "movement_counter", ""),
    ("pressure", "pressure", "hPa"),
    ("temperature", "temperature", "°C"),
    ("tx_power", "signal_strength", "dBm"),
]
_LOGGER = logger.get(__name__)


class RuuvitagWorker(BaseWorker):
    def _setup(self):
        from ruuvitag_sensor.ruuvitag import RuuviTag

        _LOGGER.info("Adding %d %s devices", len(self.devices), repr(self))
        for name, mac in self.devices.items():
            _LOGGER.debug("Adding %s device '%s' (%s)", repr(self), name, mac)
            self.devices[name] = RuuviTag(mac)

    def config(self):
        ret = []
        for name, device in self.devices.items():
            ret.extend(self.config_device(name, device.mac))
        return ret

    def config_device(self, name, mac):
        ret = []
        device = {
            "identifiers": self.format_discovery_id(mac, name),
            "manufacturer": "Ruuvi",
            "model": "RuuviTag",
            "name": self.format_discovery_name(name),
        }

        for attr, device_class, unit in ATTR_CONFIG:
            payload = {
                "unique_id": self.format_discovery_id(mac, name, device_class),
                "name": self.format_discovery_name(name, device_class),
                "state_topic": self.format_prefixed_topic(name, device_class),
                "device": device,
                "device_class": device_class,
                "unit_of_measurement": unit,
            }
            ret.append(
                MqttConfigMessage(
                    MqttConfigMessage.SENSOR,
                    self.format_discovery_topic(mac, name, device_class),
                    payload=payload,
                )
            )

        return ret

    def status_update(self):
        from bluepy import btle

        ret = []
        _LOGGER.info("Updating %d %s devices", len(self.devices), repr(self))
        for name, device in self.devices.items():
            _LOGGER.debug("Updating %s device '%s' (%s)", repr(self), name, device.mac)
            try:
                ret.extend(self.update_device_state(name, device))
            except btle.BTLEException as e:
                logger.log_exception(
                    _LOGGER,
                    "Error during update of %s device '%s' (%s): %s",
                    repr(self),
                    name,
                    device.mac,
                    type(e).__name__,
                    suppress=True,
                )
        return ret

    def update_device_state(self, name, device):
        values = device.update()

        ret = []
        for attr, device_class, _ in ATTR_CONFIG:
            try:
                ret.append(
                    MqttMessage(
                        topic=self.format_topic(name, device_class), payload=values[attr]
                    )
                )
            except KeyError:
                # The data format of this sensor doesn't have this attribute, so ignore it.
                pass

        return ret

    def device_for(self, mac):
        from ruuvitag_sensor.ruuvitag import RuuviTag

        return RuuviTag(mac)
