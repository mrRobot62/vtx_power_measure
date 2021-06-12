from os import environ, path

class Config(object):
   immersion_parameters = {
      "version" : "v",
      "avg" : "d",
      "peak" : "e",
      "unknown" : "p",
      "freq" : "f"
   }
   frequencies = [35,72,433,868,900,1200,2400,5600,5650,5700,5750,5800,5850,5900,5950,6000]
   vtx_table = {
      "A" : [5865,5845,5825,5805,5785,5765,5745,5725],
      "B" : [5733,5752,5711,5790,5809,5828,5847,5866],
      "E" : [5705,5685,5665,5645,5885,5905,5925,5945],
      "F" : [5740,5760,5780,5800,5820,5840,5860,5880],
      "R" : [5658,5695,5732,5769,5806,5843,5880,5917]
   }
   debug = True
   serial_delay = 0.5
   serial = {
      "baud" : 9600,
      "port" : '/dev/tty.usbmodem00000000001A1',
      # delay in ms per serial read
      "delay" : 500
   }
   influx_url = "http://192.168.0.251"
   influx_port = 8086
   influx_token = ""
   influx_user = ""
   influx_pw = ""
   influx_db = "FPV_VTX"
   influx_org = "LunaX"
   influx_measurement = "vtx"
   influx_line = "{0},test={1},model={2},t_band={3},t_freq={4},t_mW={5:0.2f},t_dBm={6:0.2f} mW={7:0.2f},dBm={8:0.2f},dif_mW={9:0.2f},dif_dBm={10:0.2f} {11}"
   df_header = ["TS","Test","Model","Target Band", "Target Freq","Target mW","Target dBm","Info","mW","dBm","dif_mW","dif_dBm"]
   csv_line = "{0};{1};{2};{3};{4};{5:0.2f};{6:0.2f};{7},{8:0.2f};{9:0.2f};{10:0.2f};{11:0.2f}"
   csv_fname = "VTX_{0}_{1}.csv"
   csv_sep = ";"
   csv_decimal = ","


