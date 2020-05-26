class Handler():
    def __init__(self, handler_name, handler_config, devices):
        self.name = handler_name
        self.devices = devices

    def get_device_data(self, path):
        '''
        Get data using devicename.attribute.path syntax
        '''

        # Split the path and get the device
        path = path.split('.')
        device = self.devices[path.pop(0)]
        data = device.data 
   
        # Recurse into the data using the path
        for path_entry in path[:-1]:
            data = data[path_entry]

        # The last entry in the list is the actual value
        return data[path[-1]]

    def process(self):
        '''
        Process device data
        '''
        pass

    def close(self):
        '''
        Called on shutdown
        '''
        pass
