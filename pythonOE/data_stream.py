from open_ephys.streaming import EventListener

import sys
import zmq
import flatbuffers
import numpy as np
import threading
from ContinuousData import *
import signal 

from open_ephys.control import OpenEphysHTTPServer
from controller import Controller

import json 

class DataStream(threading.Thread): 

    def __init__(self, controller, ip_address="127.0.0.1", port=5557):
        super().__init__()
        self.controller = controller

        self.repaint = False
        self.gui = OpenEphysHTTPServer()
        self.daemon = True
        self.url = "tcp://%s:%d" % (ip_address, port)

        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)
        self.socket.connect(self.url)
        self.socket.setsockopt(zmq.SUBSCRIBE, b"")

        self.stop_event = threading.Event()
        self.start()

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
        while not self.stop_event.is_set():
            try:
                parts = self.socket.recv_multipart(flags=zmq.NOBLOCK)
                
                if len(parts) == 2:

                    info = json.loads(parts[1].decode("utf-8"))
                    if info["state"]:
                        self.controller.add_event(info)

            except zmq.Again:
                # No message received
                pass
            except KeyboardInterrupt:
                print()  # Add final newline
                break
        
    def start_acquisition(self):
        if self.gui.status() != "IDLE":
            self.gui.idle()

        path, folder = self.controller.setup_file_folder()
        self.gui.set_record_path(103, str(path))
        self.gui.set_base_text(folder)
        self.gui.record()
        self.controller.is_running = True

    def stop_acquistion(self):
        self.gui.idle()
        self.controller.is_running = False

    def stop(self):
        self.gui.idle()
        self.stop_event.set()
        self.socket.close()
        self.context.term()

controller = Controller()
stream = DataStream(controller)