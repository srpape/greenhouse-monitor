import wiringpi

from .Sensor import Sensor

class ExhaustFan(Sensor):
    def __init__(self, device_name, device_config):
        super(ExhaustFan, self).__init__(device_type='exhaust', device_name=device_name, device_config=device_config)
        self.fwd_pin = int(device_config['fwd_pin'])
        self.bwd_pin = int(device_config['bwd_pin'])
        self.pwm_pin = int(device_config['pwm_pin'])

        # Prepare pins for output/pwm
        wiringpi.pinMode(self.fwd_pin, 1)
        wiringpi.pinMode(self.bwd_pin, 1)
        wiringpi.pinMode(self.pwm_pin, 2)
        wiringpi.pwmSetMode(wiringpi.PWM_MODE_MS)

        # Prepare PWM specs
        self.range = 480 # 20Khz
        self.clock = 2 # Must be at least 2
        wiringpi.pwmSetClock(self.clock)
        wiringpi.pwmSetRange(self.range)
        #freq = 19200000 / self.clock / self.range
        #print("Frequency:", freq)

        # Initialize to off
        self.data['speed'] = 0
        self.off()

    def fwd(self):
        wiringpi.digitalWrite(self.fwd_pin, 1)
        wiringpi.digitalWrite(self.bwd_pin, 0)
        self.data['state'] = 'fwd'

    def bwd(self):
        wiringpi.digitalWrite(self.bwd_pin, 1)
        wiringpi.digitalWrite(self.fwd_pin, 0)
        self.data['state'] = 'bwd'

    def off(self):
        wiringpi.digitalWrite(self.bwd_pin, 1)
        wiringpi.digitalWrite(self.fwd_pin, 1)
        self.data['state'] = 'off'

    def brake(self):
        wiringpi.digitalWrite(self.bwd_pin, 0)
        wiringpi.digitalWrite(self.fwd_pin, 0)
        self.data['state'] = 'brake'

    def set_speed(self, speed):
        if speed < 10:
            speed = 0

        if speed == self.data['speed']:
            return

        if speed == 0:
            self.off()
        else:
            self.fwd()

        self.data['speed'] = speed
        duty = int(self.range * speed / 100)
        wiringpi.pwmWrite(self.pwm_pin, duty)

    def close(self):
        '''
        Called on shutdown
        '''
        self.off()
