import serial
import os
import glob
import argparse
import re
from time import sleep
import datetime, time
from timeit import default_timer as timer
from math import log10

import pandas as pd
import sys
import termios
import atexit
from select import select
from config import Config 
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
import matplotlib.pyplot as plt
from pylab import title, figure, xlabel, ylabel, xticks, bar, legend, axis, savefig
from fpdf import FPDF


db = None           # InfluxDB device 
write = None        # InfluxDB write object

parser = argparse.ArgumentParser(description='VTX-Measurements')

parser.add_argument('-u',"--url", default="https://192.168.0.251:8086",
                    help='set URL to influxDB (https://<ip>:<port>')
parser.add_argument('-db',"--database", default="FPV_VTX",
                    help='set database name, default is FPV_VTX')
parser.add_argument('-m',"--model", default="unknown",
                    help='set vtx model id')
parser.add_argument('-i',"--info", default="",
                    help='set additional information for current measuring')
parser.add_argument('-d',"--delay", default=500, type=int, 
                    help='set delay in ms between two reads')
parser.add_argument('-t',"--time", default=60, type=int, 
                    help='set measuring time in seconds, default is 60s')
parser.add_argument('-f',"--freq", default="5850", type=str, 
                    help='set frequency')
parser.add_argument('-p',"--pwr", default="25", type=str, 
                    help='set frequency')
parser.add_argument("--param", default='d',choices=['d','p',], 
                    help='set frequency')
parser.add_argument("--influx", action="store_true", 
                    help='write into an InfluxDB')
parser.add_argument("--csv", action="store_true", 
                    help='create a csv export file')



action = parser.add_mutually_exclusive_group(required=True)         
action.add_argument('-s',"--serial", type=str,
                    help='set serial port for Immersion RF-meter')
action.add_argument("--scan", action="store_true", help='scan serial ports.')



args = parser.parse_args()


line = Config.influx_line
row_list = []
df = None
print ("-----------------------------------------")
print ("InfluxDB URL\t{}".format(args.url))
print ("InfluxDB db \t{}".format(args.database))
print ("Information \t{}".format(args.info))
print ("VTX-Model   \t{}".format(args.model))
print ("VTX-Freq    \t{}".format(args.freq))
print ("VTX-Power   \t{}".format(args.pwr))
print ("Read delay  \t{}".format(args.delay))
print ("SerialPort  \t{}".format(args.serial))
print ("")
print (args)

Config.serial_delay = args.delay / 1000

class KBHit:

    def __init__(self):
        '''Creates a KBHit object that you can call to do various keyboard things.
        '''

        if os.name == 'nt':
            pass

        else:

            # Save the terminal settings
            self.fd = sys.stdin.fileno()
            self.new_term = termios.tcgetattr(self.fd)
            self.old_term = termios.tcgetattr(self.fd)

            # New terminal setting unbuffered
            self.new_term[3] = (self.new_term[3] & ~termios.ICANON & ~termios.ECHO)
            termios.tcsetattr(self.fd, termios.TCSAFLUSH, self.new_term)

            # Support normal-terminal reset at exit
            atexit.register(self.set_normal_term)


    def set_normal_term(self):
        ''' Resets to normal terminal.  On Windows this is a no-op.
        '''

        if os.name == 'nt':
            pass

        else:
            termios.tcsetattr(self.fd, termios.TCSAFLUSH, self.old_term)


    def getch(self):
        ''' Returns a keyboard character after kbhit() has been called.
            Should not be called in the same program as getarrow().
        '''

        s = ''

        if os.name == 'nt':
            return msvcrt.getch().decode('utf-8')

        else:
            return sys.stdin.read(1)


    def getarrow(self):
        ''' Returns an arrow-key code after kbhit() has been called. Codes are
        0 : up
        1 : right
        2 : down
        3 : left
        Should not be called in the same program as getch().
        '''

        if os.name == 'nt':
            msvcrt.getch() # skip 0xE0
            c = msvcrt.getch()
            vals = [72, 77, 80, 75]

        else:
            c = sys.stdin.read(3)[2]
            vals = [65, 67, 66, 68]

        return vals.index(ord(c.decode('utf-8')))


    def kbhit(self):
        ''' Returns True if keyboard character was hit, False otherwise.
        '''
        if os.name == 'nt':
            return msvcrt.kbhit()

        else:
            dr,dw,de = select([sys.stdin], [], [], 0)
            return dr != []

    def kbenterhit(self):
        '''
        check if enter was hit
        '''
        if self.kbhit():
            c = self.getch()
            if (ord(c) == ord('\r')) or (ord(c) == ord('\n')):
                return True
        return False
        

    def kbWaitEnter(self):
        '''
        wait until enter was hit
        '''
        while True:
            if (self.kbenterhit()):
                return True

# Function to convert from mW to dBm
def mW2dBm(mW):
    mW = float(mW)
    return 10.*log10(mW)

# Function to convert from dBm to mW
def dBm2mW(dBm):
    dBm = float(dBm)
    return 10**((dBm)/10.)

def serial_ports():
    """ Lists serial port names

        :raises EnvironmentError:
            On unsupported or unknown platforms
        :returns:
            A list of the serial ports available on the system
    """
    if sys.platform.startswith('win'):
        ports = ['COM%s' % (i + 1) for i in range(256)]
    elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
        # this excludes your current terminal "/dev/tty"
        ports = glob.glob('/dev/tty[A-Za-z]*')
    elif sys.platform.startswith('darwin'):
        ports = glob.glob('/dev/tty.*')
        print ("SerialPorts")
        print (ports)
    else:
        raise EnvironmentError('Unsupported platform')

    result = []
    for port in ports:
        try:
            s = serial.Serial(port)
            s.close()
            result.append(port)
        except (OSError, serial.SerialException):
            print ("ERROR: problem serial port {}".format(str(OSError)))
            pass
    return result

def InitSerial():
   global ser
   try:
        Config.serial["port"] = args.serial
        Config.serial["delay"] = args.delay

        ser = serial.Serial(Config.serial["port"], Config.serial["baud"])
   except serial.SerialException as e:
      print("Serial device '{}' not available".format(Config.serial["port"]))
      sys.exit(1)

def InitInfluxDB(influx_url, influx_token="", influx_database=Config.influx_db):
    '''
    connect to influx database via influx_url und bind influx_database
    return a influx db object and an influx writeer
    '''
    db = InfluxDBClient(url=influx_url, token=influx_token, database=influx_database)
    Config.influx_db = influx_database
    write = None
    if db != None:
        return (db, db.write_api(write_options=SYNCHRONOUS))
    return (None, None)

def WriteTo(write_api, measurement, tag_model, tag_freq, tag_pwr, field_dbm, test_ts):
    global row_list
    '''
    influx_line = "{0},model={1},freq={2},mWatt={3} dB={4}"

    '''
    l = []
    ms = datetime.datetime.now()
    
    ts = int(time.mktime(ms.timetuple())*1000000000)
    tag_model = tag_model.replace(" ","_").upper()
    tag_dbm = mW2dBm(tag_pwr)

    field_mw = dBm2mW(field_dbm)
    if field_dbm < 0.0:
        field_dbm = 0.0
        field_mw = 0.0
    d1 = field_mw - float(tag_pwr)
    d2 = field_dbm - float(tag_dbm)

    l.append(ts)
    l.append(test_ts)
    l.append(tag_model)
    l.append(tag_freq)
    l.append(round(tag_pwr,1))
    l.append(round(tag_dbm,2))
    l.append(args.info)
    l.append(round(field_mw,2))
    l.append(round(field_dbm,2))
    l.append(round(d1,2))
    l.append(round(d2,2))

    row_list.append(dict(zip(Config.df_header, l)))
    line = Config.influx_line.format(Config.influx_measurement, test_ts, tag_model, tag_freq, tag_pwr, tag_dbm, field_mw, field_dbm,d1,d2, ts)
    print ("WRITE: {0} \t{1}".format(ms,line))

    if args.influx:
        if (field_dbm > 0.0):
            write_api.write(Config.influx_db, Config.influx_org, [line])
        else:
            print ("{0} no writing into db \t{1}".format(ms,line))


def SendImmersionRF(parameter):
    '''
    send parameter to Immersion RF meter and return restult form device
    '''
    ser.write(str.encode("{}\r".format(parameter)))
    ser.flush()
    sleep(0.1)
    bytesToRead = ser.inWaiting()
    v = ser.read(bytesToRead)
    if (parameter.lower() == Config.immersion_parameters["version"]):
        return v
    if (parameter[0].lower() == Config.immersion_parameters["freq"]):
        return v
    if (parameter == Config.immersion_parameters["avg"] or parameter == Config.immersion_parameters["peak"]):
        result = re.findall(r"[-+]?\d*\.\d+|\d+", v.decode('utf-8'))
    sleep(Config.serial_delay)    
    return float(result[0])

def searchBestFreqSetup(freq):
    last_diff = 9999
    choice = 0
    for idx, freq_rf in enumerate(Config.frequencies):
        current_diff = abs(abs(freq_rf) - int(freq))
        if current_diff == 0:
            return idx
        if current_diff < last_diff:
            last_diff = current_diff
            choice = idx
        if current_diff > last_diff:
            break
    return choice



def run():
    global line, row_list, df
    ms = datetime.datetime.now()
    id = int(time.mktime(ms.timetuple()))
    test_ts = ms.strftime("%Y%m%d") + "_" + str(id)
    kb = KBHit()
    if (args.scan):
        ports = serial_ports()
        print (ports)
        sys.exit(0)
    db = writer = None
    InitSerial()
    if args.influx:
        print ("connect InfluxDB....")
        (db, writer) = InitInfluxDB(influx_url=args.url, influx_database=Config.influx_db)
    print ("initialize Immersion RF-Meter...")
    df = pd.DataFrame(columns=Config.df_header)
    sleep(3.0)
    result = SendImmersionRF('v')
    print ("Immersion RF-Meter version: {}".format(result))
    pwr_list = args.pwr.split(',')
    freq_list = args.freq.split(',')
    for freq in freq_list:
        row_list = []
        for pwr in pwr_list:
            print("\n***************************************************************************")
            print ("Please set POWER on \tVTX to {0}mW".format(pwr))
            print ("Please set FREQ on \tVTX to {0}Mhz Freq\n".format(freq))
            freq_id = searchBestFreqSetup(freq)
            freq_rf = "F{}".format(freq_id)
            print ("Nearest frequency for ImmersionRF-Meter was set to {0}Mhz automatically".format(Config.frequencies[freq_id],freq_rf))
            print ("\nPlease set your VTX to above values - Press ENTER to start measuring")
            print("***************************************************************************")
            kb.kbWaitEnter()
            result = SendImmersionRF(freq_rf)
            start = timer()
            timeout = False
            while timeout == False:
                # prepare for kind of measurement (avg or peak)
                result = SendImmersionRF(args.param)
                #print ("{0:5f}\t{1}".format(elapsed, result))
                WriteTo(writer, 
                    Config.influx_measurement,
                    args.model,
                    int(freq),
                    float(pwr),
                    result, 
                    test_ts
                )
                end = timer()
                elapsed = end - start
                if float(elapsed) >= float(args.time):
                    timeout = True            
            print(" --- measuring for {0}mW on {1}Mhz done ---".format(float(pwr),int(freq) ))
            df = df.append(row_list,ignore_index=True)
        print ("finished in {}seconds".format(elapsed))
    print ("all power measurements done")

    now = datetime.datetime.now()
    ts = now.strftime("%Y%m%d_%H-%M-%S")
    model = args.model.replace(" ","_").upper()
    csv_fname = Config.csv_fname.format(model,ts)
    print ("creating csv export file {0}".format(csv_fname))
    df.to_csv(csv_fname, index=False, header=True, decimal=Config.csv_decimal, sep=Config.csv_sep,encoding="utf-8")
    print ("finished")

if __name__ == "__main__":
    run()


#1622899155000000000