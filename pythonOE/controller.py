from model import Model
from datetime import datetime
from pathlib import Path
import threading
import numpy as np

class Controller: 

    def __init__(self):

        
        self.selected_folder =  None
        self.is_running = False
        self.event_type = "Average"
        self.setup_event_view(3072, 96, 32, 4, 4)
        self.nbr_events = 4
        self.nbr_event_received = 0
        self.events= dict()
        
    def set_view_callback(self, view):
        self.view = view 


    def setup_file_folder(self):
        
        self.data = None
        self.events= dict()
        self.nbr_event_received = 0
        self.special_events= dict(Average=[])
        self.model.data_event = dict()

        self.data_folder= datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.data_path = Path(self.selected_folder) / self.data_folder
        self.model.file = self.data_path /r"Record Node 103\experiment1\recording1\continuous\File_Reader-100.NI-DAQmx-100.PXI-6289\continuous.dat"
        print(f"Desktop path: {self.data_path}")

        return self.selected_folder, self.data_folder

    def setup_event_view(self, num_channel, nb_col, nb_line, col_divider, line_divider):
        assert(nb_col % col_divider == 0)
        assert(nb_line % line_divider == 0)   
        self.model = Model(num_channel, nb_col, nb_line, col_divider, line_divider)

    def add_event(self, info):

        self.nbr_event_received +=1

        if self.nbr_events != 0 and self.nbr_event_received > self.nbr_events:
            return 

        print("Event occurred on TTL line " 
                + str(info['line']) 
                + " at " 
                + str(info['sample_number'] / info['sample_rate']) 
                + " seconds.")

        def add_event_in_thread():
            self.model.add_event(info)

            if self.nbr_events != 0 and self.nbr_event_received >= self.nbr_events:
                self.view.stop_acquistion_from_thread()

            self.view.add_dropdown_options(str(info['sample_number']))

            self.events[str(info['sample_number'])] = info['sample_number']
            self.special_events["Average"].append(info['sample_number'])

            self.view.update_sources()

        threading.Thread(target=add_event_in_thread).start()

    def update_nbr_events(self, new):
        self.nbr_events = new

    def update_snapshot(self, event_duration):

        self.model.reset_xy(event_duration)
        for value in self.events:
            self.model.compute_event(self.events[value])

        self.view.update_sources()
    
    def update_freq(self, lc=None, hc=None):

        if lc is not None:
            self.model.lc = lc
        
        if hc is not None:
            self.model.hc = hc 

        for value in self.events:
            self.model.compute_event(self.events[value])

        self.view.update_sources()


    def get_data_event(self):

        if self.event_type in self.events:
            return self.model.x, self.model.data_event[self.events[self.event_type]]
        
        elif self.event_type in self.special_events:

            all_ts = self.special_events[self.event_type]
            d = np.stack([self.model.data_event[ts] for ts in all_ts])
            return self.model.x, np.mean(d, axis=0)

                

