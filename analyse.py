import serial
import os
import glob
import argparse
import re
import json
import random
import string
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

parser.add_argument('-l',"--load", type=str, help='load an existing csv file for reporting, no measurements are done')

args = parser.parse_args()

line = Config.influx_line
row_list = []
df = None
print ("-------------------------------------------------------")
print ("Loading an existing data file to create an report")
print ("Import csv \t{}".format(args.load))
print ("")
print ("-------------------------------------------------------")


def mW2dBm(mW):
    ''' convert mW to dBm '''
    mW = float(mW)
    return 10.*log10(mW)

def dBm2mW(dBm):
    ''' convert dBm to mW '''
    dBm = float(dBm)
    return 10**((dBm)/10.)

def run():
   global line, row_list, df
   ms = datetime.datetime.now()
   id = int(time.mktime(ms.timetuple()))
   test_ts = ms.strftime("%Y%m%d") + "_" + str(id)

   df = pd.read_csv(args.load, sep=Config.csv_sep, decimal=Config.csv_decimal, header=0, encoding="utf-8")
   print ("Data size: \t{0}".format(df.shape))
   print ("Data cols: \t{0}".format(df.columns))   

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
#    if args.load is None:
    run()
