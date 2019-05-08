class Handler():
    def __init__(self, handler_name, handler_config, devices):
        self.name = handler_name

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
