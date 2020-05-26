#!/usr/bin/env python3
import configparser
import urllib.request
import json
import logging
import wiringpi
import time #TODO: Remove

from apscheduler.schedulers.background import BackgroundScheduler

from flask import Flask
from flask import make_response
from flask import request
from flask_restful import Api, Resource, reqparse

from sendmail import sendmail

class Subscription(Resource):
    def get(self, name):
        pass

class GreenhouseMonitor():
    def __init__(self):
        pass

    def run(self):
        # Prepare GPIO
        wiringpi.wiringPiSetupGpio()

        # Prepare scheduler
        scheduler = BackgroundScheduler(daemon=True)
        scheduler.start()

        # Parse configuration
        config_path = '/etc/greenhouse-monitor.conf'
        config = configparser.ConfigParser()
        config.read(config_path)

        # Prepare devices
        self.devices = {}
        devices = __import__('devices')
        for device_name in config['main']['devices'].split(','):
            device_config = config[device_name]
            class_ = getattr(devices, config[device_name]['type'])
            self.devices[device_name] = class_(device_name=device_name, device_config=device_config)

        # Prepare data sinks
        self.handlers = {}
        handlers = __import__('handlers')
        for handler_name in config['main']['handlers'].split(','):
            handler_config = config[handler_name]
            class_ = getattr(handlers, config[handler_name]['type'])
            self.handlers[handler_name] = class_(handler_name=handler_name, handler_config=handler_config, devices=self.devices)

        # Run an initial update
        self.run_handlers()

        # Start recurring jobs
        scheduler.add_job(self.run_handlers, 'interval', seconds=10, coalesce=True)

        # Add flask endpoints
        app = Flask(__name__)
        api = Api(app)
        api.add_resource(Subscription, "/subscribe/<string:name>")

        # Start up flask
        try:
            # With the reloader enabled, apscheduler executes twice, one in each process
            # We could probably fix this correctly, but just disabling the reloader for now
            app.run(debug=True,host='0.0.0.0', use_reloader=False)
        finally:
            print("GPIO Cleanup")

            for device_name in self.devices:
                self.devices[device_name].close()
            for handler_name in self.handlers:
                self.handlers[handler_name].close()

    def update_devices(self):
        for device_name in self.devices:
            #start = time.time()
            self.devices[device_name].update()
            #end = time.time()
            #print("Updated device " + device_name + ": " + str(end - start) + 's')

    def run_handlers(self):
        self.update_devices()
        for handler_name in self.handlers:
            self.handlers[handler_name].process()



# Main method
if __name__ == "__main__":
    monitor = GreenhouseMonitor()
    monitor.run()





