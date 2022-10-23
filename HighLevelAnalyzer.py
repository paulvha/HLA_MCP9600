# High Level Analyzer
# For more information and documentation, please go to https://support.saleae.com/extensions/high-level-analyzer-extensions
'''
This High level Analyzer is displaying information that is exchanged between an MCP9600 and an MCU (like an Arduino) on the I2C.
It will decode (as much as possible) the data that is read/written to a register on the MCP9600. With data that is read from the MCP9600
the register, it will try to decode what is known or else the raw received data is displayed.

October 2022, version 1.0.1
* Couple of cosmetic changes and erata cleared

October 2022, version 1.0.0
Paul van Haastrecht

'''
from saleae.analyzers import HighLevelAnalyzer, AnalyzerFrame, StringSetting, NumberSetting, ChoicesSetting

# Registers with decoders
HOT_JUNC_TEMP           = '0x0'
DELTA_JUNC_TEMP         = '0x1'
COLD_JUNC_TEMP          = '0x2'
RAW_ADC                 = '0x3'
SENSOR_STATUS           = '0x4'
THERMO_SENSOR_CONFIG    = '0x5'
DEVICE_CONFIG           = '0x6'
ALERT1_CONFIG           = '0x8'
ALERT2_CONFIG           = '0x9'
ALERT3_CONFIG           = '0xa'
ALERT4_CONFIG           = '0xb'
ALERT1_HYSTERESIS       = '0xc'
ALERT2_HYSTERESIS       = '0xd'
ALERT3_HYSTERESIS       = '0xe'
ALERT4_HYSTERESIS       = '0xf'
ALERT1_LIMIT            = '0x10'
ALERT2_LIMIT            = '0x11'
ALERT3_LIMIT            = '0x12'
ALERT4_LIMIT            = '0x13'
DEVICE_ID               = '0x20'

# all known MCP9600 register names (also those without decoder)
MCP9600_Registers = {
    '0x0' : 'HOT_JUNC_TEMP: ',            # read only
    '0x1' : 'DELTA_JUNC_TEMP: ',          # read only
    '0x2' : 'COLD_JUNC_TEMP: ',           # read only
    '0x3' : 'RAW_ADC: ',                  # read only
    '0x4' : 'SENSOR_STATUS: ',
    '0x5' : 'THERMO_SENSOR_CONFIG: ',
    '0x6' : 'DEVICE_CONFIG: ',
    '0x8' : 'ALERT1_CONFIG: ',
    '0x9' : 'ALERT2_CONFIG: ',
    '0xa' : 'ALERT3_CONFIG: ',
    '0xb' : 'ALERT4_CONFIG: ',
    '0xc' : 'ALERT1_HYSTERESIS: ',
    '0xd' : 'ALERT2_HYSTERESIS: ',
    '0xe' : 'ALERT3_HYSTERESIS: ',
    '0xf' : 'ALERT4_HYSTERESIS: ',
    '0x10': 'ALERT1_LIMIT: ',
    '0x11': 'ALERT2_LIMIT: ',
    '0x12': 'ALERT3_LIMIT: ',
    '0x13': 'ALERT4_LIMIT: ',
    '0x20': 'DEVICE_ID: ',                # read only
}

''' JUNC_TEMP '''
# default for resolution
DEV_RESOLUTION = 0.0625

''' THERMO_SENSOR_CONFIG register '''
Thermocouple_Type = {
    0b000: 'TYPE_K',
    0b001: 'TYPE_J',
    0b010: 'TYPE_T',
    0b011: 'TYPE_N',
    0b100: 'TYPE_S',
    0b101: 'TYPE_E',
    0b110: 'TYPE_B',
    0b111: 'TYPE_R'
}

''' DEVICE_CONFIG register '''
Thermocouple_Resolution = {
    0b00: 'RES_18_BIT',
    0b01: 'RES_16_BIT',
    0b10: 'RES_14_BIT',
    0b11: 'RES_12_BIT'
}

Burst_Sample = {
    0b000: 'SAMPLES_1',
    0b001: 'SAMPLES_2',
    0b010: 'SAMPLES_4',
    0b011: 'SAMPLES_8',
    0b100: 'SAMPLES_16',
    0b101: 'SAMPLES_32',
    0b110: 'SAMPLES_64',
    0b111: 'SAMPLES_128'
}

shutdown_modes = {
    0x00: 'Normal',
    0x01: 'Shutdown',
    0x02: 'Burst'
}

# High level analyzers must subclass the HighLevelAnalyzer class.
class Hla(HighLevelAnalyzer):

    # An optional list of types this analyzer produces, providing a way to customize the way frames are displayed in Logic 2.
    result_types = {
            "ping": {
                'format': 'Ping: {{{data.address}}}'
            },
            "pingERR": {
                'format': 'PingERR: {{{data.address}}}'
            },
            "ReadErr": {
                'format': 'ReadErr: {{{data.address}}}'
            },
            "hi2c": {
                'format': '{{data.description}} {{data.action}} [ {{data.data}} ]'
            },
            "read": {
                'format': '{{data.description}}'
            },
            "resp": {
                'format': '{{data.description}} data[{{data.count}}]: [ {{data.data}} ]'
            }
    }

    temp_frame = None               # Working frame to build output
    register_type = None            # holds the register read or written
    data_byte = 0                   # holds the most recent data read
    ObtainMode = False              # True : Assume a register read request was send
    data_unknown = True             # True : No additional data received (indicating read request)
    request_register_type = None    # Hold a register that has an assumed read requested pending

    reg_data = 0                    # needed to read 16/32-bit registers
    reg_count = 0                   # needed to read 16/32-bit registers

    def __init__(self):
        '''
        Initialize HLA.

        Settings can be accessed using the same name used above.
        '''
        pass

    def decode(self, frame: AnalyzerFrame):
        '''
        Process a frame from the input analyzer, and optionally return a single `AnalyzerFrame` or a list of `AnalyzerFrame`s.

        The type and data values in `frame` will depend on the input analyzer.
        '''
        # set our frame to an error frame, which will eventually get over-written as we get data.
        if self.temp_frame is None:
            self.temp_frame = AnalyzerFrame("hi2c", frame.start_time, frame.end_time, {
                    "address": "error",
                    "description" :"",
                    "data" : "",
                    "action" :"",
                    "count": 0
                }
            )

        if frame.type == "error":
            self.temp_frame.data["description"] = "error"

        if frame.type == "address":
            address_byte = frame.data["address"][0]
            self.temp_frame.data["address"] = hex(address_byte)
            self.temp_frame.data["read"] = frame.data["read"]
            self.temp_frame.data["ack"] = frame.data["ack"]     # true if ACK else NACK

        if frame.type == "data":
            self.data_byte = frame.data["data"][0]

            # if waiting on responds from an assumed read request
            if self.ObtainMode == True:
                # restore the saved register to (potentially) decode the responds
                self.register_type = self.request_register_type

            # no register known yet
            if self.register_type == None:
                self.register_type = hex(self.data_byte)

            # select decoder for register (if available)

            elif self.register_type == HOT_JUNC_TEMP:
                self.decode_JUNC_TEMP(self.data_byte)

            elif self.register_type == COLD_JUNC_TEMP:
                self.decode_JUNC_TEMP(self.data_byte)

            elif self.register_type == DELTA_JUNC_TEMP:
                self.decode_JUNC_TEMP(self.data_byte)

            elif self.register_type == ALERT1_HYSTERESIS:
                self.decode_ALERT_HYSTERESIS(self.data_byte)

            elif self.register_type == ALERT2_HYSTERESIS:
                self.decode_ALERT_HYSTERESIS(self.data_byte)

            elif self.register_type == ALERT3_HYSTERESIS:
                self.decode_ALERT_HYSTERESIS(self.data_byte)

            elif self.register_type == ALERT4_HYSTERESIS:
                self.decode_ALERT_HYSTERESIS(self.data_byte)

            elif self.register_type == ALERT1_CONFIG:
                self.decode_ALERT_CONFIG(self.data_byte)

            elif self.register_type == ALERT2_CONFIG:
                self.decode_ALERT_CONFIG(self.data_byte)

            elif self.register_type == ALERT3_CONFIG:
                self.decode_ALERT_CONFIG(self.data_byte)

            elif self.register_type == ALERT1_LIMIT:
                self.decode_ALERT_LIMIT(self.data_byte)

            elif self.register_type == ALERT2_LIMIT:
                self.decode_ALERT_LIMIT(self.data_byte)

            elif self.register_type == ALERT3_LIMIT:
                self.decode_ALERT_LIMIT(self.data_byte)

            elif self.register_type == ALERT4_LIMIT:
                self.decode_ALERT_LIMIT(self.data_byte)

            elif self.register_type == ALERT4_CONFIG:
                self.decode_ALERT_CONFIG(self.data_byte)

            elif self.register_type == THERMO_SENSOR_CONFIG:
                self.decode_THERMO_SENSOR_CONFIG(self.data_byte)

            elif self.register_type == SENSOR_STATUS:
                self.decode_SENSOR_STATUS(self.data_byte)

            elif self.register_type == DEVICE_CONFIG:
                self.decode_DEVICE_CONFIG(self.data_byte)

            elif self.register_type == DEVICE_ID:
                self.decode_DEVICE_ID(self.data_byte)

            elif self.register_type == RAW_ADC:
                self.decode_RAW_ADC(self.data_byte)

            # oh oh no decoder available for this register
            # either not created (yet) or not enough information to create decoder
            # for now supplying the raw data
            else:
                self.add_databyte()

        if frame.type == "stop":
            self.temp_frame.end_time = frame.end_time

            # if we had a read request before (single register) assume this is a responds on the read request
            if self.ObtainMode == True:
                desc = self.temp_frame.data["description"]
                self.temp_frame.data["description"] = ""
                self.add_description("Responds:")
                self.add_description(desc)
                self.ObtainMode = False

                new_frame = self.temp_frame

            # No data received in this frame
            elif self.data_unknown == True:

                # if only the I2C-address was received.
                if self.register_type == None:

                    # if only the address was received. assume a 'I2C-ping' to test the device is there
                    # only the first PING is acknowledged by the MCP9600
                    if self.temp_frame.data["ack"] == True:
                        new_frame = AnalyzerFrame("ping", self.temp_frame.start_time, frame.end_time, {
                            "address": self.temp_frame.data["address"],
                        }
                    )
                    # the next I2c_address + write BIT AND the first I2C_address + read BIT after a PING gets a NACK
                    else:
                        # In case of a read and NO bytes.. that is an error
                        if self.temp_frame.data["read"] == True:
                            new_frame = AnalyzerFrame("ReadErr", self.temp_frame.start_time, frame.end_time, {
                            "address": self.temp_frame.data["address"],
                            }
                        )
                        # An I2C address + write attempt that did not succesfull
                        else:
                            new_frame = AnalyzerFrame("pingERR", self.temp_frame.start_time, frame.end_time, {
                            "address": self.temp_frame.data["address"],
                            }
                        )
                # so we did get a byte and if only ONE byte assume this is a register read request
                else:
                    self.add_description("Obtain ")
                    self.add_register(self.register_type)
                    self.request_register_type = self.register_type
                    self.ObtainMode = True

                    new_frame = AnalyzerFrame("read", self.temp_frame.start_time, frame.end_time, {
                        "address": self.temp_frame.data["address"],
                        "description" : self.temp_frame.data["description"]
                        }
                )
            # this is a "normal" write to a register
            else:
                new_frame = self.temp_frame
                self.ObtainMode = False

            # reset different variables
            self.data_unknown = True
            self.temp_frame = None
            self.register_type = None

            return new_frame

    def add_databyte(self):
        """ Just add data byte """
        self.temp_frame.data["count"] += 1
        if len(self.temp_frame.data["data"]) > 0:
            self.temp_frame.data["data"] += ", "
        self.temp_frame.data["data"] += hex(self.data_byte)
        self.temp_frame.data["description"] += "data only"

    def add_action(self,act):
        """ add comma separated action """
        if len(self.temp_frame.data["action"]) > 0:
            self.temp_frame.data["action"] += ", "
        self.temp_frame.data["action"] += act

    def add_description(self,act):
        """ add comma separated description """
        if len(self.temp_frame.data["description"]) > 0:
            self.temp_frame.data["description"] += ", "
        self.temp_frame.data["description"] += act
        self.data_unknown = False

    def add_register(self,act):
        """ Add a register to description """
        if act in MCP9600_Registers:
            reg = MCP9600_Registers[act]
            self.add_description(reg)
        else:
            self.add_description("unknown")

    def decode_JUNC_TEMP(self,data_byte):
        """ HOT_JUNC_TEMP, DELTA_JUNC_TEMP, COLD_JUNC_TEMP """
        # get the 16 bits
        if self.reg_count < 2:
            self.reg_data = self.reg_data << 8
            self.reg_data = self.reg_data | data_byte
            self.reg_count += 1

        if self.reg_count == 2:

            self.add_register(self.register_type)

            # The Ambient register contains the thermocouple cold-junction temperature or the device ambient temperature
            # data. Bits 1 and 0 may remain clear (‘0’) depending on the status of the Resolution setting, bit 7 of
            # Device Config register. As such the resolution calculation stays the same  * 0.0625
            Temp = self.reg_data * DEV_RESOLUTION

            # if sign bit(s) is set, the temperature is negative
            if self.reg_data & 0x80:
                Temp = Temp - 4096

            # set for 2 decimals
            format_float = "{:.2f}".format(Temp)

            self.add_description("Temp: ")
            self.temp_frame.data["description"] += str(format_float)
            self.temp_frame.data["description"] += "°C"

            self.temp_frame.data["count"] += 2
            self.temp_frame.data["data"] += hex(self.reg_data)

            self.reg_data = 0
            self.reg_count = 0

    def decode_DEVICE_ID(self,data_byte):

        # get the 16 bits
        if self.reg_count < 2:
            self.reg_data = self.reg_data << 8
            self.reg_data = self.reg_data | data_byte
            self.reg_count += 1

        if self.reg_count == 2:
            self.add_register(self.register_type)

            dev = (self.reg_data >> 8)
            self.temp_frame.data["description"] += hex(dev)

            maj = (self.reg_data >> 4) & 0x0f
            self.add_description("Maj: ")
            self.temp_frame.data["description"] += hex(maj)

            minn = self.reg_data & 0x0f
            self.add_description("Min: ")
            self.temp_frame.data["description"] += hex(minn)

            self.temp_frame.data["count"] += 2
            self.temp_frame.data["data"] += hex(self.reg_data)

            self.reg_data = 0
            self.reg_count = 0

    def decode_ALERT_HYSTERESIS(self, data_byte):
        """ ALERT1_HYSTERESIS, ALERT2_HYSTERESIS, ALERT3_HYSTERESIS """
        self.add_register(self.register_type)

        self.add_description("hysteresis: ")
        self.temp_frame.data["description"] += str(data_byte)

        self.temp_frame.data["count"] += 1
        self.temp_frame.data["data"] += hex(data_byte)

    def decode_ALERT_LIMIT(self,data_byte):
        """ ALERT1_LIMIT, ALERT2_LIMIT, ALERT3_LIMIT """
        # get the 16 bits
        if self.reg_count < 2:
            self.reg_data = self.reg_data << 8
            self.reg_data = self.reg_data | data_byte
            self.reg_count += 1

        if self.reg_count == 2:

            self.add_register(self.register_type)

            f = float(self.reg_data >> 4)
            if (self.reg_data & 0x8):
                 f = f + 0.5
            if (self.reg_data & 0x4):
                 f = f + 0.25

            self.add_description("Limit: ")
            self.temp_frame.data["description"] += str(f)

            self.temp_frame.data["count"] += 2
            self.temp_frame.data["data"] += hex(self.reg_data)

            self.reg_data = 0
            self.reg_count = 0

    def decode_THERMO_SENSOR_CONFIG(self, data_byte):

        self.add_register(self.register_type)

        self.add_description("Type: ");
        term = (data_byte >> 4) & 0x7
        if term in Thermocouple_Type:
            TermType = Thermocouple_Type[term]
            self.temp_frame.data["description"] += TermType
        else:
            self.temp_frame.data["description"] += "unknown"

        self.add_description("filter(")
        Filter = data_byte & 0x3
        self.temp_frame.data["description"] +=(str(Filter))
        self.temp_frame.data["description"] += ")"

        if Filter == 0:
            self.temp_frame.data["description"] += " Off"

        elif Filter == 2:
            self.temp_frame.data["description"] += " Minimum"

        elif Filter == 4:
            self.temp_frame.data["description"] += " Mid"

        elif Filter == 7:
            self.temp_frame.data["description"] += " Max"

        self.temp_frame.data["count"] += 1
        self.temp_frame.data["data"] += hex(data_byte)

    def decode_RAW_ADC(self, data_byte):

        # get the 24 bits
        if self.reg_count < 3:
            self.reg_data = self.reg_data << 8
            self.reg_data = self.reg_data | data_byte
            self.reg_count += 1

        if self.reg_count == 3:

            self.add_register(self.register_type)

            self.temp_frame.data["description"] += "Raw: "
            self.temp_frame.data["description"] +=str(self.reg_data)

            self.temp_frame.data["count"] += 3
            self.temp_frame.data["data"] += hex(self.reg_data)

            self.reg_data = 0
            self.reg_count = 0

    def decode_DEVICE_CONFIG(self, data_byte):

        self.add_register(self.register_type)

        self.add_action("Cold Res: ")

        # ambient / cold resolution
        if data_byte & 0x80:
            self.temp_frame.data["action"] += "0.25"
        else:
            self.temp_frame.data["action"] += "0.0625"

        self.add_action("Hot Res: ")
        res = (data_byte >> 5) & 0x3
        if res in Thermocouple_Resolution:
            self.temp_frame.data["action"] += Thermocouple_Resolution[res]
        else:
            self.temp_frame.data["action"] += "unknown"

        samples = (data_byte >> 2) & 0x3
        if samples in Burst_Sample:
            self.add_action(Burst_Sample[samples])
        else:
            self.add_action("Samples?")

        self.add_action("Shutdown: ")
        shut = data_byte & 0x3
        if shut in shutdown_modes:
            self.temp_frame.data["action"] += shutdown_modes[shut]
        else:
            self.temp_frame.data["action"] += "unknown"

        self.temp_frame.data["count"] += 1
        self.temp_frame.data["data"] += hex(data_byte)


    def decode_ALERT_CONFIG(self,data_byte):
        ''' ALERT1_CONFIG, ALERT2_CONFIG, ALERT3_CONFIG '''
        self.add_register(self.register_type)

        if (data_byte & 0x01):
            self.add_action("Alert enabled")
        else:
            self.add_action("Alert disabled")

        if (data_byte & 0x02):
            self.add_action("Interrupt_mode:")
        else:
            self.add_action("Comparator_mode")

        if (data_byte & 0x04):
            self.add_action("Active_high")
        else:
            self.add_action("Active_low")

        if (data_byte & 0x8):
            self.add_action("Alert on falling")
        else:
            self.add_action("Alert on rising")

        if (data_byte & 0x10):
            self.add_action("Monitor: T_C cold-junction")
        else:
            self.add_action("Monitor: T_H thermocouple")

        if (data_byte & 0x80):
            self.add_action("Clears interrupt")
        else:
            self.add_action("Cleared interrupt")

        self.temp_frame.data["count"] += 1
        self.temp_frame.data["data"] += hex(data_byte)

    def decode_SENSOR_STATUS(self,data_byte):

        self.add_register(self.register_type)

        if (data_byte & 0x01):
            self.add_action("TX > AL1")
        else:
            self.add_action("TX < AL1")

        if (data_byte & 0x02):
            self.add_action("TX > AL2")
        else:
            self.add_action("TX < AL2")

        if (data_byte & 0x04):
            self.add_action("TX > AL3")
        else:
            self.add_action("TX < AL3")

        if (data_byte & 0x8):
            self.add_action("TX > AL4")
        else:
            self.add_action("TX < AL4")

        if (data_byte & 0x10):
            self.add_action("EMF error")
        else:
            self.add_action("EMF OK")

        if (data_byte & 0x20):
            self.add_action("Thermocouple Shorted")

        if (data_byte & 0x40):
            self.add_action("conversion complete")

        if (data_byte & 0x80):
            self.add_action("Burst complete")

        self.temp_frame.data["count"] += 1
        self.temp_frame.data["data"] += hex(data_byte)
