from epsolar_tracer.client import EPsolarTracerClient
from epsolar_tracer.enums.RegisterTypeEnum import RegisterTypeEnum

from .Sensor import Sensor

class EPSolarCharger(Sensor):
    def __init__(self, device_name, device_config):
        super(EPSolarCharger, self).__init__(device_type='charger', device_name=device_name, device_config=device_config)

        self._client = epsolar = EPsolarTracerClient(port=device_config['port'])

        self.data['battery'] = {}
        self.data['charging'] = {}
        self.data['discharging'] = {}

    def update(self):
        # Get the battery temperature
        response = self._client.read_input(RegisterTypeEnum.BATTERY_TEMPERATURE)
        self.data['battery']['temperature'] = self.celcius_to_fahrenheit(response.value)

        # Get the battery state of charge
        response = self._client.read_input(RegisterTypeEnum.BATTERY_SOC)
        self.data['battery']['state_of_charge'] = response.value

        # Get the battery watts
        response = self._client.read_input(RegisterTypeEnum.CHARGING_EQUIPMENT_OUTPUT_POWER)
        self.data['battery']['output_power'] = response.value

        # Get the equipment temperature
        response = self._client.read_input(RegisterTypeEnum.TEMPERATURE_INSIDE_EQUIPMENT)
        self.data['temperature'] = self.celcius_to_fahrenheit(response.value)

        # Get the solar watts
        response = self._client.read_input(RegisterTypeEnum.CHARGING_EQUIPMENT_INPUT_POWER)
        self.data['charging']['input_power'] = response.value

        # Get the load watts
        response = self._client.read_input(RegisterTypeEnum.DISCHARGING_EQUIPMENT_OUTPUT_POWER)
        self.data['discharging']['output_power'] = response.value