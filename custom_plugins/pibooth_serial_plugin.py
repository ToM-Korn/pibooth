"""Plugin for serial communication with an microcontroller for extended control of lights and other things """

import pibooth
from pibooth.utils import LOGGER
import subprocess as sp
import serial
import os

__version__ = "0.0.1"
#
# class PiboothSerial():
#
#
#     def __init__(self):
#         self.port = None
#         self.com = None
#         req = sp.run("ls /dev | grep USB", shell=True, capture_output=True)
#
#         if req.returncode == 0:
#             port = req.stdout.decode().strip()
#             self.port = "/dev/" + port
#             self.com = serial.Serial(self.port, timeout=1)
#
#         LOGGER.info("Communication Port for Serial is: ", self.port)


port = None
com = None

req = sp.run("ls /dev | grep USB", shell=True, capture_output=True)

if req.returncode == 0:
    port = req.stdout.decode().strip()
    port = "/dev/" + port
    com = serial.Serial(port, timeout=1)

    LOGGER.info(f"Communication Port for Serial is: {port}")
@pibooth.hookimpl
def state_wait_enter():
    # set the lights to Pulse
    com.write(b'LIGPUL\n')
    LOGGER.info("Light set to Pulse")

@pibooth.hookimpl
def state_wait_exit():
    # a photo will be taken
    # set the lights to full power
    com.write(b'LIGON\n')
    LOGGER.info("Light set to ON")

@pibooth.hookimpl
def state_wait_do():
    # wait is in loop
    # in this position we read the serial
    # if the command is "SHUTDOWN"
    # we confirm the shutdown and poweroff
    line = com.readline()
    if line != b'':
        line = line.decode("UTF-8")
        line = line.strip()
        if line != '':
            LOGGER.info(f"Serial Input Line: {line}")
            if line == 'SHUTDOWN':
                LOGGER.info("Shutting down System")
                os.system('poweroff')


