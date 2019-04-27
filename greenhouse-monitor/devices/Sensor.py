import json
import urllib.request

class Sensor:
    def __init__(self, device_name, device_type, device_config):
        self.device_type = device_type
        self.device_name = device_name
        self.__device_path = self.device_type + '/' + self.device_name
        self.data = {}

    def celcius_to_fahrenheit(self, tempC):
        return tempC * 9/5.0 + 32

    def fill_data(self, data):
        data[self.device_name] = self.data

    def update(self):
        '''
        Update the sensor data
        '''
        pass

    def notify(self):
        '''
        Push an unsolicited update to SmartThings
        '''
        body = self.get_body()
        headers = {
            'Content-Type': 'application/json',
            'Content-Length': len(body),
            'Device': self.__device_path
        }
        if smartthings_notify_url:
            req = urllib.request.Request(smartthings_notify_url, method='NOTIFY', headers=headers, data=body)
            urllib.request.urlopen(req, timeout=15)

    def get_response(self):
        '''
        Get a response for an HTTP GET or POST
        '''
        resp = make_response(self.get_body())
        resp.headers['Device'] = self.__device_path
        return resp

    def get_body(self):
        '''
        Get the body we send out for response/notify
        '''
        body = json.dumps(self.data).encode()
        return body

    def close(self):
        '''
        Called on shutdown
        '''
        pass
