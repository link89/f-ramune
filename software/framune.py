#!/usr/bin/env python3

import os
import struct
import sys
import serial
from collections import OrderedDict

BAUD_RATE = 115200
TIMEOUT = 1

PROTOCOL_VERSION = 0
ENDIANNESS = '>'

def serial_without_dtr(port, *args, **kwargs):
    """Construct a Serial object with DTR immediately disabled.
    On systems where pySerial supports this, this will prevent an Arduino from
    resetting when a serial connection is opened. On other systems, a hardware
    workaround (e.g. a 10 µF capacitor between RST and ground) is needed.
    """
    ser = serial.Serial(None, *args, **kwargs)
    ser.port = port
    ser.dtr = 0
    if port is not None: # To match what pySerial does.
        ser.open()
    return ser

class Framune(object):
    def __init__(self, serial_port):
        if hasattr(serial_port, 'port'):
            self.serial_port = serial_port.port
            self._serial = serial_port
        else:
            self.serial_port = serial_port
            self._serial = serial_without_dtr(serial_port, BAUD_RATE, timeout=TIMEOUT)
        self._chip = MemoryChip(None, None, None, None, framune=self)
    
    def __exit__(self, *args):
        self.close()

    def close(self):
        self._serial.close()
    
    @property
    def chip(self):
        return self._chip
    
    @chip.setter
    def chip(self, chip):
        self._set_and_analyze_chip(chip)
    
    def _read(self, length=1):
        try:
            data = self._serial.read(length)
            if len(data) < length:
                raise TimeoutError
        except (serial.SerialTimeoutException, TimeoutError):
            raise TimeoutError("F-Ramune did not respond in time.")
        else:
            return data
    
    def _write(self, data):
        self._serial.write(data)

    def _read_uint(self, fmt, length):
        return struct.unpack(fmt, self._read(length))[0]
    
    def _write_uint(self, fmt, n):
        self._write(struct.pack(fmt, n))

    def _read_byte(self):
        return self._read_uint(ENDIANNESS + 'B', 1)
    
    def _write_byte(self, n):
        self._write_uint(ENDIANNESS + 'B', n)
    
    def _read_uint16(self):
        return self._read_uint(ENDIANNESS + 'H', 2)

    def _write_uint16(self, n):
        self._write_uint(ENDIANNESS + 'H', n)

    def _command(self, command):
        self._write_byte(command)
        if self._read_byte() == command:
            self._write_byte(0x00)
        else:
            self._write_byte(0x01)
            raise ConnectionError("Command didn't reach F-Ramune intact.")
    
    def _set_and_analyze_chip(self, chip):
        self._command(0x01)
        self._write(chip.known_status_to_bytes())
        self._write(chip.to_bytes())
        self._chip = MemoryChip.from_bytes(
            self._read(MEMORY_CHIP_KNOWN_DATA_STRUCTURE_SIZE),
            self._read(MEMORY_CHIP_DATA_STRUCTURE_SIZE),
            framune=self
        )

    def get_version(self):
        """Return the protocol version of the F-Ramune."""
        self._command(0x00)
        return self._read_uint16()
    
    def version_matches(self):
        """Return True if the F-Ramune has the same protocol version
        as the script does; False if not.
        """
        return self.get_version() == PROTOCOL_VERSION
    
    def read(self, address, length):
        """Return `length` bytes read starting at `address` from the memory
        chip currently connected to the F-Ramune.
        """
        pass
    
    def write(self, address, data):
        """Write the bytes `data` to the memory chip currently connected to
        the F-Ramune, starting at `address`."""
        pass

MEMORY_CHIP_DATA_STRUCTURE = OrderedDict((
    ('is_operational', '?'),
    ('size', 'I'),
    ('is_nonvolatile', '?'),
    ('is_eeprom', '?')
))
MEMORY_CHIP_DATA_STRUCTURE_FMT = ENDIANNESS + \
    ''.join(MEMORY_CHIP_DATA_STRUCTURE.values())
MEMORY_CHIP_DATA_STRUCTURE_SIZE = \
    struct.calcsize(MEMORY_CHIP_DATA_STRUCTURE_FMT)
MEMORY_CHIP_KNOWN_DATA_STRUCTURE_FMT = ENDIANNESS + \
    '?' * len(MEMORY_CHIP_DATA_STRUCTURE)
MEMORY_CHIP_KNOWN_DATA_STRUCTURE_SIZE = \
    struct.calcsize(MEMORY_CHIP_KNOWN_DATA_STRUCTURE_FMT)
class MemoryChip(object):
    def __init__(self, is_operational=None, size=None,
                 is_nonvolatile=None, is_eeprom=None, framune=None):
        self.is_operational = is_operational
        self.size = size
        self.is_nonvolatile = is_nonvolatile
        self.is_eeprom = is_eeprom
        self._framune = framune
    
    @classmethod
    def from_bytes(cls, known, properties, framune=None):
        known = struct.unpack(MEMORY_CHIP_KNOWN_DATA_STRUCTURE_FMT, known)
        values = struct.unpack(MEMORY_CHIP_DATA_STRUCTURE_FMT, properties)
        return cls(**{
            k: (v if is_known else None)
            for k, v, is_known
            in zip(MEMORY_CHIP_DATA_STRUCTURE, values, known)
        }, framune=framune)
    
    def __repr__(self):
        return "<MemoryChip: {}>".format(', '.join('{}={}'.format(
            attr, getattr(self, attr)
        ) for attr in MEMORY_CHIP_DATA_STRUCTURE))

    def known_status_to_bytes(self):
        return bytes(int(getattr(self, attr) is not None)
            for attr in MEMORY_CHIP_DATA_STRUCTURE)

    def to_bytes(self):
        return struct.pack(MEMORY_CHIP_DATA_STRUCTURE_FMT, *(
            getattr(self, attr) or 0 for attr in MEMORY_CHIP_DATA_STRUCTURE
        ))
        #return b''.join(struct.pack(ENDIANNESS + v, int(getattr(self, k) or 0))
        #    for k, v in MEMORY_CHIP_DATA_STRUCTURE.items())

def main(*argv):
    script_name = os.path.split(__file__)[-1]
    try:
        serial_port = argv[0]
    except IndexError:
        print("Usage: {} <serial port>", file=sys.stderr)
    
    with Framune(serial_port) as framune:
        print("Connected F-Ramune protocol version: {}".format(framune.get_version))

    return 0

if __name__ == '__main__':
    sys.exit(main(*sys.argv[1:]))