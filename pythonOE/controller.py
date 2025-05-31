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
        self.model = None

        self.nbr_events = 4
        self.nbr_event_received = 0
        self.events= dict()
        self.special_events= dict(Average=[])
        self.register_line = np.zeros(32)
        self.register_line[8] = 1
        self.event_duration = 0.1
        self.lc = 1
        self.hc = 200
        self.order = 4

    def set_view_callback(self, view):
        self.view = view 

    def setup_file_folder(self):
  
        self.events= dict()
        self.nbr_event_received = 0
        self.special_events= dict(Average=[])
        self.model.data_event = dict()
        
        self.data_folder= datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.model.data_path = Path(self.selected_folder) / self.data_folder
        self.model.file = None

        print(f"Desktop path: {self.model.data_path}")

        return self.selected_folder, self.data_folder

    def setup_event_view(self, num_channel, nb_col, nb_line, col_divider, row_divider):
        self.model = Model(num_channel, nb_col, nb_line, col_divider, row_divider)
        self.model.reset_xy(self.event_duration)
        self.model.lc = self.lc
        self.model.hc = self.hc
        self.model.order = self.order

    def add_event_line(self, line):
        self.register_line[line] = 1

    def remove_event_line(self, line):
        self.register_line[line] = 0

    def add_event(self, info):

        if not self.register_line[info["line"]]:
            print("Event from line " + str(info["line"]) + " ignored")
            return 

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
        self.event_duration = event_duration

        if self.model is not None:
            self.model.reset_xy(event_duration)
            for value in self.events:
                self.model.compute_event(self.events[value])

        self.view.update_sources()
    
    def update_freq(self, lc=None, hc=None, order=None):
        if order is not None:
            self.order = order

        if lc is not None:
            self.lc = lc 
        
        if hc is not None:
            self.hc = hc 

        if self.model is None: 
            return
        
        self.model.lc = self.lc
        self.model.hc = self.hc
        self.model.order = self.order

        for value in self.events:
            self.model.compute_event(self.events[value])

        self.view.update_sources()


    def get_data_event(self):
        
        if self.event_type in self.events:
            return self.model.x, self.model.data_event[self.events[self.event_type]]
        
        elif self.event_type in self.special_events:

            all_ts = self.special_events[self.event_type]
            if len(all_ts) == 0: 
                return self.model.x, [np.zeros(int(self.model.event_snapshot_duration * self.model.fs)*2)]*int(self.model.num_channel/(self.model.col_divider*self.model.row_divider))

            d = np.stack([self.model.data_event[ts] for ts in all_ts])
            return self.model.x, np.mean(d, axis=0)

    def get_full_data(self, ncol, nrow):
        if self.model is None: 
            return False, None, None

        if self.is_running:
            self.model.read_data(recursive=False)
        
        if self.model.data is None:
            return False, None, None
        x, y = self.model.get_full_signal(nrow, ncol)
        return True, x, y



