#!/usr/bin/env python3

import fcntl
import json
import time

from epsolar_tracer.client import EPsolarTracerClient
from epsolar_tracer.enums.RegisterTypeEnum import RegisterTypeEnum

class EPSolarCharger:
    def __init__(self):
        self._client = EPsolarTracerClient(port="/dev/ttyAMA0")

    def update(self):
        result = {"time": int(time.time())}

        for reg in RegisterTypeEnum:
            suffix = reg.name[-2:]
            if suffix in ("_L", "_H"):
                continue

            response = self._client.read_input(reg)
            result[reg.name] = {}
            result[reg.name]["value"] = response.value
            result[reg.name]["name"] = response.register.name
            result[reg.name]["description"] = response.register.description
            result[reg.name]["unit"] = response.register.unit()

        return result

if __name__ == "__main__":
    e = EPSolarCharger()
    output_filename = "/tmp/epsolar.json"

    while True:
        output = e.update()

        with open(output_filename, 'w') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write(json.dumps(output))

        time.sleep(2)

