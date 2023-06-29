# acquire.py Acquire a pulse train from an IR remote
# Supports NEC protocol.
# For a remote using NEC see https://www.adafruit.com/products/389

# Author: Peter Hinch
# Copyright Peter Hinch 2020 Released under the MIT license

from machine import Pin, freq
from sys import platform

from utime import sleep_ms, ticks_us, ticks_diff
from ir_rx import IR_RX


class IR_GET(IR_RX):
    def __init__(self, pin, nedges=100, twait=100, display=True):
        self.display = display
        super().__init__(pin, nedges, twait, lambda *_ : None)
        self.data = None

    def decode(self, _):
        def near(v, target):
            return target * 0.8 < v < target * 1.2
        lb = self.edge - 1  # Possible length of burst
        if lb < 3:
            return  # Noise
        burst = []
        for x in range(lb):
            dt = ticks_diff(self._times[x + 1], self._times[x])
            if x > 0 and dt > 10000:  # Reached gap between repeats
                break
            burst.append(dt)
        lb = len(burst)  # Actual length
        # Duration of pulse train 24892 for RC-5 22205 for RC-6
        duration = ticks_diff(self._times[lb - 1], self._times[0])

        if self.display:
            for x, e in enumerate(burst):
                print('{:03d} {:5d}'.format(x, e))
            print()
            # Attempt to determine protocol
            print('Unknown protocol start {} {} Burst length {} duration {}'.format(burst[0], burst[1], lb, duration))

            print()
        self.data = burst
        # Set up for new data burst. Run null callback
        self.do_callback(0, 0, 0)

    def acquire(self):
        while self.data is None:
            sleep_ms(5)
        self.close()
        return self.data

def test(PIN):
    irg = IR_GET(PIN)
    print('Waiting for IR data...')
    return irg.acquire()
