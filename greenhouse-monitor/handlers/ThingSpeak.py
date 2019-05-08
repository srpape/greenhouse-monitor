import certifi
import urllib3

from .Handler import Handler

class ThingSpeak(Handler):
    def __init__(self, handler_name, handler_config, devices):
        super(ThingSpeak, self).__init__(handler_name=handler_name, handler_config=handler_config, devices=devices)
        self.baseURL = 'https://api.thingspeak.com/update?api_key=%s' % handler_config['api_key'] 
        self.fields = []
        self.http = urllib3.PoolManager(cert_reqs='CERT_REQUIRED', ca_certs=certifi.where())

        for option in handler_config:
            if option.startswith('field'):
                path = handler_config[option].split('.')
                device = devices[path.pop(0)]
                self.fields += [[ option, path, device.data ]]
                

    def process(self):
        '''
        Used to log the data to thingspeak
        '''

        request = ''
 
        # Build our request
        for field in self.fields:
            request += '&' + field[0] + '='

            # Recurse into the options 
            path = field[1]
            data = field[2] 
            for path_entry in path[:-1]:
                data = data[path_entry]

            # The last entry in the list is the actual value
            request += str(data[path[-1]]) 

        url = self.baseURL + request

        try:
            f = self.http.request('GET', url)
            f.close()
        except Exception as e:
            print('ThingSpeak Error:', e)
            # For some reason the data was not accepted
            # ThingSpeek gives a lot of 500 errors 
            pass        
