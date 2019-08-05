"""Module to control a Sharp Aquos Remote Control enabled TV."""
import pkgutil
import yaml
import serial
import logging

_LOGGER = logging.getLogger(__name__)

class TV(object):
    """
    Description:
        Class representing a Sharp Aquos TV
        Based on documentation from:
            http://files.sharpusa.com/Downloads/ForHome/HomeEntertainment/LCDTVs/Manuals/2014_TV_OM.pdf

    Author: Jeffrey Moore <jmoore987@yahoo.com>

    URL: http://github.com/jmoore/sharp_aquos_rc
    """
    _VALID_COMMAND_MAPS = ["eu", "us", "cn", "jp"]

    def __init__(self, url, baudrate=9600, stopbits=serial.STOPBITS_ONE,
                 bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE,
                 timeout=2, write_timeout=2, command_map='us'):
        """
        Initialize the client.
        """
        self._port = serial.serial_for_url(url, do_not_open=True)
        self._port.baudrate = baudrate
        self._port.stopbits = stopbits
        self._port.bytesize = bytesize
        self._port.parity = parity
        self._port.timeout = timeout
        self._port.write_timeout = write_timeout
        self._port.open()
        if command_map not in self._VALID_COMMAND_MAPS:
            raise ValueError("command_layout should be one of %s, not %s" % (str(self._VALID_COMMAND_MAPS), command_map))

        #stream = pkgutil.get_data("sharp_aquos_rc", "commands/%s.yaml" % command_map)
        stream = open('/config/custom_components/aquostv2/commands/{}.yaml'.format(command_map))
        self.command = yaml.load(stream, Loader=yaml.FullLoader)

    def _send_command_raw(self, command, opt=''):
        """
        Description:

            The TV doesn't handle long running connections very well,
            so we open a new connection every time.
            There might be a better way to do this,
            but it's pretty quick and resilient.

        Returns:
            If a value is being requested ( opt2 is "?" ),
            then the return value is returned.
            If a value is being set,
            it returns True for "OK" or False for "ERR"
        """
        # According to the documentation:
        # http://files.sharpusa.com/Downloads/ForHome/
        # HomeEntertainment/LCDTVs/Manuals/tel_man_LC40_46_52_60LE830U.pdf
        # Page 58 - Communication conditions for IP
        # The connection could be lost (but not only after 3 minutes),
        # so we need to the remote commands to be sure about states
        # clear

        self._port.reset_output_buffer()
        self._port.reset_input_buffer()
        # Send command
        if opt != '':
            command += str(opt)
        command = command.ljust(8)+'\r\n'
        command = command.encode('utf-8')
        _LOGGER.debug('*Sending "%s"', command)
        self._port.write(command)
        self._port.flush()
        # receive
        result = bytearray()
        while True:
            char = self._port.read(1)
            if char is None:
                break
            if not char:
                raise serial.SerialTimeoutException(
                    'Connection timed out! Last received bytes {}'
                    .format([hex(a) for a in result]))
            result += char
            if result and result[-1:] == b'\r':
                break
        status = bytes(result).strip().decode("utf-8")
        _LOGGER.debug('*Received "%s"', status)
        
        if "OK" in status:
            return True
        if "ERR" in status:
            return False
        try:
            return int(status)
        except ValueError:
            return status

    def _check_command_name(self, name, dicitionary):
        if name not in dicitionary:
            raise ValueError(name + "command is not in list")

    def _send_command(self, name, parameter=''):
        if isinstance(name, str):
            self._check_command_name(name, self.command)
            command = self.command[name]
        elif isinstance(name, list):
            dictionary = self.command
            for val in name:
                self._check_command_name(val, dictionary)
                if isinstance(dictionary[val], dict):
                    dictionary = dictionary[val]
                else:
                    command = dictionary[val]
        return self._send_command_raw(command, parameter)

    def info(self):
        """
        Description:

            Returns dict of information about the TV
            name, model, version

        """
        return {"name": self._send_command('name'),
                "model": self._send_command('model'),
                "version": self._send_command('version'),
                "ip_version": self._send_command('ip_version')
               }

    def power_on_command_settings(self, opt='?'):
        """
        Description:

            Manage whether or not the TV will respond to power() on/off commands
            Call with no arguments to get current setting

        Arguments:
            opt: integer
                0: disabled
                1: accepted via RS232
                2: accepted via TCP/IP
        """
        return self._send_command('power_control', opt)

    def power(self, opt='?'):
        """
        Description:

            Power On/Off
            Call with no arguments to get current setting

        Arguments:
            opt: integer
                0: Off
                1: On
        """
        return self._send_command('power', opt)

    def get_input_list(self):
        """
        Description:

            Get input list
            Returns an dict of all available input keys and names

        """
        inputs = {}
        for key in self.command['input']:
            inputs[key] = self.command['input'][key]['name']
        return inputs

    def input(self, opt='?'):
        """
        Description:

            Set the input
            Call with no arguments to get current setting

        Arguments:
            opt: string
                Name provided from input list or key from yaml ("HDMI 1" or "hdmi_1")
        """
        if opt == '?':
            index = self._send_command('input_index')
            if index == False:
                # return self.command['input']['tv']['index']
                return False
            else:
                for key in self.command['input']:
                    if (self.command['input'][key]['index'] == index):
                        return self.command['input'][key]['index']
        else:
            for key in self.command['input']:
                if (key == opt) or (self.command['input'][key]['index'] == opt):
                    return self._send_command(['input', key, 'command'])
            return False

    def av_mode(self, opt='?'):
        """
        Description:

            Set the A/V Mode
            Call with no arguments to get current setting

        Arguments:
            opt: integer
                0: Toggle
                1: Standard (ENERGYSTAR)
                2: Movie
                3: Game
                4: User
                5: Dynamic (Fixed)
                6: Dynamic
                7: PC
                8: x.v. Color
                13: Vintage Movie
                14: Standard 3D
                15: Movie 3D
                16: Game 3D
                17: Movie THX
                100: Auto
        """
        return self._send_command('av_mode', opt)

    def volume(self, opt='?'):
        """
        Description:

            Set the Volume
            Call with no arguments to get current setting

        Arguments:
            opt: integer
            0 - 100: Volume Level
        """
        return self._send_command('volume', opt)

    def volume_up(self):
        """
        Description:
            Change the Volume +1
        """
        return self._send_command('volume_up')

    def volume_down(self):
        """
        Description:
            Change the Volume +1
        """
        return self._send_command('volume_down')

    def view_mode(self, opt='?'):
        """
        Description:

            Set the View Mode
            Call with no arguments to get current setting

        Arguments:
            opt: integer
                0: Toggle [AV]
                1: Side Bar [AV]
                2: S. Stretch [AV]
                3: Zoom [AV]
                4: Stretch [AV]
                5: Normal [PC]
                6: Zoom [PC]
                7: Stretch [PC]
                8: Dot by Dot [PC]
                9: Full Screen [AV]
                10: Auto
                11: Original
        """
        return self._send_command('view_mode', opt)

    def mute(self, opt='?'):
        """
        Description:

            Mute On/Off
            Call with no arguments to get current setting

        Arguments:
            opt: integer
                0: Toggle
                1: On
                2: Off
        """
        return self._send_command('mute', opt)

    def surround(self, opt='?'):
        """
        Description:

            Set Surround Sound mode
            Call with no arguments to get current setting

        Arguments:
            opt: integer
                0: Toggle
                1: On / Normal
                2: Off
                4: 3D Hall
                5: 3D Movie
                6: 3D Standard
                7: 3D Stadium
        """
        return self._send_command('sound_mode', opt)

    def sleep(self, opt='?'):
        """
        Description:

            Set Sleep Timer
            Call with no arguments to get minutes until poweroff

        Arguments:
            opt: integer
                0: Off
                1: 30 minutes
                2: 60 minutes
                3: 90 minutes
                4: 120 minutes
        """
        return self._send_command('sleep', opt)

    def analog_channel(self, opt='?'):
        """
        Description:

            Change Channel (Analog)
            Call with no arguments to get current setting

        Arguments:
            opt: integer
                (1-135): Channel
        """
        return self._send_command('analog_channel', opt)

    def digital_channel_air(self, opt1='?', opt2='?'):
        """
        Description:

            Change Channel (Digital)
            Pass Channels "XX.YY" as TV.digital_channel_air(XX, YY)

        Arguments:
            opt1: integer
                1-99: Major Channel
            opt2: integer (optional)
                1-99: Minor Channel
        """
        if opt1 == '?':
            parameter = '?'
        elif opt2 == '?':
            parameter = str(opt1).rjust(4, "0")
        else:
            parameter = '{:02d}{:02d}'.format(opt1, opt2)
        return self._send_command('digital_channel_air', parameter)

    def digital_channel_cable(self, opt1='?', opt2=0):
        """
        Description:

            Change Channel (Digital)
            Pass Channels "XXX.YYY" as TV.digital_channel_cable(XXX, YYY)

        Arguments:
            opt1: integer
                1-999: Major Channel
            opt2: integer (optional)
                0-999: Minor Channel
        """
        if opt1 == '?':
            parameter = '?'
        elif self.command['digital_channel_cable_minor'] == '':
            parameter = str(opt1).rjust(4, "0")
        else:
            self._send_command('digital_channel_cable_minor', str(opt1).rjust(3, "0"))
            parameter = str(opt2).rjust(3, "0")
        return self._send_command('digital_channel_cable_major', parameter)

    def channel_up(self):
        """
        Description:
            Change the Channel +1
        """
        self._send_command('channel_up')

    def channel_down(self):
        """
        Description:
            Change the Channel -1
        """
        self._send_command('channel_down')

    def get_remote_button_list(self):
        """
        Description:

            Get remote button list
            Returns an list of all available remote buttons

        """
        remote_buttons = []
        for key in self.command['remote']:
            if self.command['remote'][key] != '':
                remote_buttons.append(key)
        return remote_buttons

    def remote_button(self, opt):
        """
        Description:

            Press a remote control button

        Arguments:
            opt: string
                key provided from input list
        """
        return self._send_command(['remote', opt])
