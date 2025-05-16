from open_ephys.streaming import EventListener

from datetime import datetime
import sys
import zmq
import flatbuffers
import numpy as np
import threading
from ContinuousData import *
import signal 
import time
from pathlib import Path
from open_ephys.control import OpenEphysHTTPServer
from bokeh.io import curdoc


import json 

class DataStream(threading.Thread): 

    def __init__(self, ip_address="127.0.0.1", port=5557):
        super().__init__()
        address = 'localhost' # IP address of the computer running Open Ephys

        self.gui = OpenEphysHTTPServer()
        self.daemon = True
        self.url = "tcp://%s:%d" % (ip_address, port)

        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)
        self.socket.connect(self.url)
        self.socket.setsockopt(zmq.SUBSCRIBE, b"")
        self.fs = 1953 #Hz
        self.event_snapshot_duration = 0.1
        self.num_channel = 3072
        
        self.stop_event = threading.Event()
        self.data =None
        self.last_event = 0
        print("Initialized EventListener at " + self.url)

    def run(self):
        """
        Starts the listening process, with separate callbacks
        for TTL events and spikes.

        The callback functions should be of the for:

          function(info)

        where `info` is a Python dictionary.

        See the README file for the dictionary contents.

        """

        print("Starting EventListener")
        self.start_acquisition()
        while not self.stop_event.is_set():
            try:
                parts = self.socket.recv_multipart(flags=zmq.NOBLOCK)
                if len(parts) == 2:

                    info = json.loads(parts[1].decode("utf-8"))

                    self.ttl_callback(info)
            except zmq.Again:
                # No message received
                pass
            except KeyboardInterrupt:
                print()  # Add final newline
                break
            
    def get_full_signal(self, channel):
        return self.read_data()[:, channel]


    def ttl_callback(self, info):
        print("Event occurred on TTL line " 
                + str(info['line']) 
                + " at " 
                + str(info['sample_number'] / info['sample_rate']) 
                + " seconds.")


        print("event " + str(info['sample_number']))
        self.read_data()
        self.last_event = info['sample_number']

    def read_data(self):
        try: 
            data = np.memmap(self.file, mode="r", dtype="int16")
            samples = data.reshape(
                    (
                        len(data) // self.num_channel,
                        self.num_channel,
                    )
            )
        except ValueError:
            time.sleep(1)
            print("retry reading file.")
            self.read_data()
            return

        self.data = samples.reshape(-1, 32, 96)

    def start_acquisition(self):


        # Get path to the current user's Desktop
        path = Path.home() / "Desktop" / "data"
        data_folder= datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.data_path = path / data_folder
        self.file = self.data_path /r"Record Node 103\experiment1\recording1\continuous\File_Reader-100.NI-DAQmx-100.PXI-6289\continuous.dat"
        print(f"Desktop path: {self.data_path}")
        
        self.gui.set_record_path(103, str(path))
        self.gui.set_base_text(data_folder)
        self.gui.record()

    def stop_acquistion(self):

        self.gui.idle()

    def stop(self):
        self.gui.idle()
        self.stop_event.set()
        self.socket.close()
        self.context.term()

# Initialize your data stream
stream = DataStream()