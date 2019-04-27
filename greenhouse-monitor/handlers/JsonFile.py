import json

from .Handler import Handler

class JsonFile(Handler):
    def __init__(self, handler_name, handler_config, devices):
        super(JsonFile, self).__init__(handler_name=handler_name, handler_config=handler_config, devices=devices)
        self.path = handler_config['path'].strip()
        self.devices = devices

    def process(self):
        '''
        Used to log JSON for the web interface
        '''
        data = {}
        for device_name in self.devices:
            self.devices[device_name].fill_data(data)

        with open('/tmp/greenhouse_state.json', 'w') as outfile:
            json.dump(data, outfile)