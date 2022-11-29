# VTX power measurment tool

Python script based on a pandas library. It can be used to work with an Immersion RF-Meter v2.

This script is not finished at all and in an alpha-release status ;-).

## Note
This software is tested on OSX only and should be running on Linux as well. Working unter Windows is ongoing.

> This is a quick & dirty implementation to compare different VTX boards on my workbench - and what can I say - none of the cheap Banggood / AliExpress China VTX boards came close to the manufacturer's stated maximum output power. <br> Most 800mW VTX delivered on average between 500-650mw. I tested about 10-12 different VTX boards. <br><br>**Buy cheap, buy twice**

**In comparision to a TBS-Sixty9 vtx no China crap comes into the range of TBS !**

# Immersion RF-Meter V2
https://www.immersionrc.com/fpv-products/rfpwrv2/

For this tool the Immersion RF-Meter V2 is used and connected via USB to the host.
This little RF-Meter use a simple CDC parameters for communication.

# Workflow
A couple of different parameters controll the worklow
* number of different frequencies
* number of different power (mW) 
* Parameters like "delay" or "time" are used to set number of readings per second and how long a measurment per frequence and per power takes

System read the first frequency and the first power configuration and wait for user to configure connected vtx-board. If done press **ENTER**.

## Example terminal output
````
***************************************************************************
Please set POWER on     VTX to 200mW
Please set FREQ on      VTX to 5785Mhz Freq

Nearest frequency for ImmersionRF-Meter was set to 5800Mhz automatically

Please set your VTX to above values - Press ENTER to start measuring
***************************************************************************
````


Now the system measures `"time"` seconds and collect data. In this case loop through all power configurations. If done, loop through all frequencies

# Stored data
| Attribute | csv | InfluxDB | Comment |
|:---|:--:|:--:|:---|
| Model | x | x | Model/Type of VTX board |
| Test | x | x | InfluxDB tag: unique timestamp for the complete run |
| Band | x | x | InfluxDB tag: VTX Band (like A, B, H, I, R, ...) |
| Info | x |  | only output to CSV, additional information pased on paramter --info |
| t_mw | x | x | InfluxDB tag: target mw (e.g. 25mW, 100mW, 200mW, ...) |
| t_dbm | x | x | InfluxDB tag: target mBm (e.g. 14.0 dBm, ...) |
| mw | x | x | InfluxDB field key = mW, field value = measured mw |
| dbm | x | x | InfluxDB field key = dbm, field value = calculated from read mW |
| diff_mw | x | x | InfluxDB field key = diff_mw, field value = target_mW - mW |
| diff_dbm | x | x | InfluxDB field key = diff_dbm, field value = target_dbm - dbm |
| timestamp |  | x | InfluxDB timestamp unix format in nanoseconds (ns) |

# Starting parameters
This python script do not have any graphical output, it's designed as a pure terminal script with output on console.

## Arguments
<todo>
  
## Examples
<todo>
  



# InfluxDB & Grafana
It's possible to store data into a InfluxDB V2 database. Generating output plots can be done with grafana.

A simple dashboard is included in folder

Via parameter it's possible to include output to this database

# CSV output
Via parameter it's possible to create from all data an output csv file.
Filename includes model name and a timestamp.
Default separator is `";"` - can be adjusted inside `config.py`

# Used Libraries
* Pandas
* InfluxDBClient
* Matplotlib
* FPDF

# Developer hints
<todo>
  


# History
|Version|Date|Info|
|:---|:---|:---|
|0.1|06-21|initial|
