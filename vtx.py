import serial
import os
import glob
import argparse
import re
import json
import random
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
import seaborn as sns

db = None           # InfluxDB device 
write = None        # InfluxDB write object

parser = argparse.ArgumentParser(description='VTX-Measurements')

#
# Selection either or 
#
# -v : loading a vtx table and start measuring
# -l : load an existing csv result file and do some statistics
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument('-v',"--vtx", type=str, help='set betaflight vtx table (JSON-File)')
group.add_argument('-l',"--load", type=str, help='load an existing csv file for reporting, no measurements are done')


# if set, than only this frequencies are used
parser.add_argument('-b',"--band", type=str, help='set which band should be used. Only a single band is allowed')
parser.add_argument('-c',"--channels", type=str, help='set which channels (frequencies) should be used (comma spepareted list)')
parser.add_argument('-p',"--power", type=str, help='set which power should be used (comma spepareted list)')

# if influx is used, this is the url from InfluxDB Server
parser.add_argument('-u',"--url", default="https://192.168.0.251:8086", help='set URL to influxDB (https://<ip>:<port>')
# influxDB database name                    
parser.add_argument('-db',"--database", default="FPV_VTX", help='set database name, default is FPV_VTX')
parser.add_argument("--influx", action="store_true", help='write into an InfluxDB')

# Which vtx-model is used, some addition information for reporting
parser.add_argument('-m',"--model", type=str, default="unknown", help='set vtx model id')
parser.add_argument('-i',"--info", type=str, default="", help='set additional information for current measuring')
parser.add_argument("--csv", action="store_true", help='create a csv export file')
parser.add_argument("--demo", action="store_true", help='do not use Immersion RF-Meter, simulate values (random)')


# technical background
parser.add_argument("--delay", default=500, type=int, help='set delay in ms between two reads')
parser.add_argument("--count", default=100, type=int, help='set number of measurements')
# maybe deprecated for future releases
parser.add_argument("--param", default='d',choices=['d','p',], help='set frequency')

# serial port for your Immersion RF-Meter 
action = parser.add_mutually_exclusive_group(required=True)         
action.add_argument("--serial", type=str, help='set serial port for Immersion RF-meter')
action.add_argument("--scan", action="store_true", help='scan serial ports.')

args = parser.parse_args()


class BF_VTX_Table:
    bf_vtx_file = None
    number_channels = 0
    number_bands = 0
    list_bands = []
    pwr_list = []
    def __init__(self, vtxFile=None):
        if vtxFile is not None:
            self.load(vtxFile)
        pass

    def load(self, vtxFile):
        # read file
        with open(vtxFile, 'r') as myfile:
            self.bf_vtx_file=json.load(myfile)
        self.getNumberOfChannels()
        self.getNumberOfChannels()
        pass

    def getNumberOfChannels(self):
        self.number_channels = len(self.bf_vtx_file["vtx_table"]["bands_list"][0]["frequencies"])
        return self.number_channels

    def getNumberOfBands(self):
        self.number_bands = len(self.bf_vtx_file["vtx_table"]["bands_list"])
        return self.number_bands 

    def getBand(self, letter='A'):
        try:
            band = next(i for i in self.bf_vtx_file["vtx_table"]["bands_list"] if i['letter']==letter)
        except:
            band = None
        return band

    def getBands(self):
        self.band_list = []
        bl = self.bf_vtx_file["vtx_table"]["bands_list"]
        for band in bl:
            self.band_list.append(band['letter'])
        return self.band_list

    def getChannel(self, bandletter, id=1):
        pass

    def getChannels(self, band='A'):
        vtx_band = self.getBand(band)
        return vtx_band['frequencies']
        

    def getVTXTable(self):
        vtx_table = None
        return vtx_table

    def getPowerList(self):       
        self.pwr_list = [] 
        pl = self.bf_vtx_file["vtx_table"]["powerlevels_list"]
        for p in pl:
            self.pwr_list.append(int(p['label']))

        return self.pwr_list


line = Config.influx_line
row_list = []
df = None
if args.demo:
    print ("**********************************")
    print ("** DEMO ** DEMO ** DEMO ** DEMO **")
    print ("**********************************")

print ("-----------------------------------------")
print ("Information\t\t{}".format(args.info))
print ("SerialPort      \t{}".format(args.serial))

if args.influx:
    print ("\nInfluxDB Details")
    print ("InfluxDB URL\t\t{}".format(args.url))
    print ("InfluxDB db \t\t{}".format(args.database))
if args.vtx:
    print ("\nVTX-Details")
    print ("BF-vtx_table\t\t{}".format(args.vtx))

    print ("VTX-model       \t{}".format(args.model))   
    print ("VTX-Info        \t{}".format(args.info))   
    if args.band:
        print ("use only this bands sets")
        print ("\tVTX-Band \t{}".format(args.band))
    if args.channels:
        print ("use only this channels sets")
        print ("\tVTX-Channels\t{}".format(args.channels))
    if args.power:
        print ("use only this power sets")
        print ("\tVTX-Power\t{}".format(args.power))

    print ("\nMeasurment-Details")
    print ("count           \t{}".format(args.delay))
    print ("Read delay      \t{}".format(args.delay))
    #print (args)
    print ("-------------------------------------------------------")

else:
    print ("-------------------------------------------------------")
    print ("Loading an existing data file to create an report")
    print ("Import csv \t{}".format(args.load))
    print ("")
    print ("no writing back into influx, no csv export")
    print ("-------------------------------------------------------")

 
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

def mW2dBm(mW):
    ''' convert mW to dBm '''
    mW = float(mW)
    return 10.*log10(mW)

def dBm2mW(dBm):
    ''' convert dBm to mW '''
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
    ''' setup serial port for Immerstion RF-Meter '''
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

def WriteTo(write_api, measurement, tag_model, tag_band, tag_freq, tag_pwr, field_dbm, test_ts):
    global row_list
    '''
    write measurement dataframe. If influx db is activated, write directly to database as lineprotocol
    '''
    l = []
    ms = datetime.datetime.now()
    
    ts = int(time.mktime(ms.timetuple())*1000000000)
    tag_model = tag_model.replace(" ","_").upper()
    tag_dbm = round(mW2dBm(tag_pwr),3)

    field_mw = round(dBm2mW(field_dbm),3)
    if field_dbm < 0.0:
        field_dbm = 0.0
        field_mw = 0.0
    d1 = field_mw - float(tag_pwr)
    d2 = field_dbm - float(tag_dbm)

    l.append(ts)
    l.append(test_ts)
    l.append(tag_model)
    l.append(tag_band)
    l.append(tag_freq)
    l.append(round(tag_pwr,1))
    l.append(round(tag_dbm,2))
    l.append(args.info)
    l.append(round(field_mw,2))
    l.append(round(field_dbm,2))
    l.append(round(d1,2))
    l.append(round(d2,2))

    row_list.append(dict(zip(Config.df_header, l)))
    line = Config.influx_line.format(Config.influx_measurement, test_ts, tag_model, tag_band, tag_freq, tag_pwr, tag_dbm, field_mw, field_dbm,d1,d2, ts)
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
    if args.demo:
        # Immersion RF-Meter returns values in dBm
        # 14 dBm = 25mW
        return round(random.uniform(13.0, 15.0),3)

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
    return float(result[0])

def searchBestFreqSetup(freq):
    '''
    search the best setup for Immersion RF-Meter based on configurated frequency of vtx

    Parameter:
    freq    configured frequence in vtx

    Retunr:
    frequence for Immersion RF-Meter
    '''
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

    bf_vtx = BF_VTX_Table(args.vtx)
    #band = bf_vtx.getBand('A')
    #band = bf_vtx.getBand('B')
    #band = bf_vtx.getBand('X')

    if args.power:
        pwr_list = args.power.split(',')
    else:
        pwr_list = bf_vtx.getPowerList()

    if args.band:
        band_list = args.band.split(',')
    else:
        band_list = bf_vtx.getBands()

    kb = KBHit()
    if (args.scan):
        ports = serial_ports()
        print (ports)
        sys.exit(0)

    db = writer = None
    if not args.demo:
        InitSerial()
        print ("initialize Immersion RF-Meter...")
        sleep(3.0)
        result = SendImmersionRF('v')
        print ("Immersion RF-Meter version: {}".format(result))

    if args.influx:
        print ("connect InfluxDB....")
        (db, writer) = InitInfluxDB(influx_url=args.url, influx_database=Config.influx_db)

    df = pd.DataFrame(columns=Config.df_header)

    #
    # 
    cnt = 0
    print("\n\n---- START ----\n")
    all_s = timer()
    for pwr in pwr_list:
        pwr = int(pwr)  # if set via parameter list is a string list
        print ("--------------------------------")
        print ("\tSet VTX-power")
        print ("--------------------------------")
        print ("Measuring this bands: \t{0}".format(band_list))
        print ("\nSet your VTX to => {0}mW and press ENTER".format(pwr))
        kb.kbWaitEnter()

        for band in band_list:
            if args.channels:
                # please note: if you use channels via parameter
                # check if this frequencies are available for given band
                channel_list = args.channels.split(',')
            else:
                channel_list = bf_vtx.getChannels(band)
            print ("\n--------------------------------")
            print ("\tSet VTX-band")
            print ("--------------------------------")
            print ("Measuring this channels: \t{0}".format(channel_list))
            print ("\nSet your VTX to => BAND: {0} and press ENTER".format(band))
            kb.kbWaitEnter()
            channel_id = 1
            for channel in channel_list:
                channel = channel.strip()
                print ("\n--------------------------------")
                print ("\tSet VTX-channel")
                print ("--------------------------------")
                print ("\nSet your VTX to => Band {0} and Channel({1}): {2} and press ENTER".format(band, channel_id, channel))
                kb.kbWaitEnter()
                result = SendImmersionRF(channel)
                cnt = 0
                chnl_s = timer()
                while cnt < args.count:
                    result = float(SendImmersionRF(args.param))
                    cnt = cnt + 1
                    WriteTo(writer, 
                        Config.influx_measurement,
                        args.model,
                        band,
                        int(channel),
                        float(pwr),
                        result, 
                        test_ts
                    )
                    print ("{0:03d}\tPower {1:#3d}mW, Band {2}, Channel({3}) {4}Mhz ".format(cnt, pwr,band,channel_id, channel))
                    sleep(Config.serial_delay)

                chnl_e = timer() - chnl_s
                df = df.append(row_list, ignore_index=True)
                print (">>> Overall channel measuring \t{}".format(str(datetime.timedelta(seconds=chnl_e))))
                channel_id = channel_id + 1
                pass
            pass
        pass

    all_e = timer() - all_s
    print ("\n\n")
    print ("-----------------------------------------------")
    print ("Overall measuring timing\t{0}".format(str(datetime.timedelta(seconds=all_e))))
    print ("-----------------------------------------------")
    '''
    for freq in freq_list:
        row_list = []
        f_timer = timer()
        #
        # iterate through all frequencies
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
            timeout = False
            counter = 0
            p_timer = timer()
            #
            # do as many measurements for current power and frequence as configured via parameter
            #
            while counter <= args.count:
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
                counter = counter + 1
                sleep(Config.serial_delay)    
                print("{2:04d} --- measuring for {0}mW on {1}Mhz done  ---".format(float(pwr),int(freq), counter ))
                pass #while
            
            e_timer = timer() - p_timer
            df = df.append(row_list,ignore_index=True)
            print (">>> mW measuring finished in {}seconds".format(e_timer))

            pass # for pwr_list

        e_timer = timer() - f_timer        
        print ("finished in {}seconds".format(e_timer))
    print ("*******************************************")
    print ("*       all power measurements done       *")
    print ("*******************************************")
    '''
    #
    # create a csv for this measurments
    if (args.csv):
        now = datetime.datetime.now()
        ts = now.strftime("%Y%m%d_%H-%M-%S")
        model = args.model.replace(" ","_").upper()
        csv_fname = Config.csv_fname.format(model,ts)
        if args.demo:
            csv_fname = "DEMO_" + csv_fname
        print ("creating csv export file {0}".format(csv_fname))
        df.to_csv(csv_fname, index=False, header=True, decimal=Config.csv_decimal, sep=Config.csv_sep,encoding="utf-8")
        print ("finished")


def report(df=None, csv_files=None):
    '''
    create a report from dataframe

    Parameter:
    df  Dataframe with measurements. If none, load an csv file
    csv_file CSV-File to load. If df is not none, csv parameter is ignored
    '''
    if (df is None) and (csv_files is not None):
        df = pd.DataFrame()
        list = csv_files.split(';')
        for f in list:
            tmp = pd.read_csv(f, sep=Config.csv_sep, decimal=Config.csv_decimal, header=0, encoding="utf-8")
            df = df.append(tmp)

        print ("Data size: \t{0}".format(df.shape))
        print ("Data cols: \t{0}".format(df.columns))
    else:
        pass
    # --------- reporting / statistic -----------------------

    # group data : model / target freq / target mw
    group_mfw = df.groupby(['Model','Target Freq','Target mW']).agg({'mW':['count','mean', 'min','max','std']},{'dBm':['mean']})
    group_mfw.colums = ['mw_count','dBm_mean','mw_mean', 'mw_min', 'mw_max','mw_std'] 
    group_mfw = group_mfw.reset_index()
    print ("\n\n")
    print ("** Stastic 1 : grouping by model/freq/power **")
    print (group_mfw)
    #out = plt.figure()
    #bp = df.boxplot(column=['mW'], by='Model')
    #out.savefig("test.png", format="png")

if __name__ == "__main__":
    if args.load is None:
        run()
    else:
        report(None, args.load)


#1622899155000000000