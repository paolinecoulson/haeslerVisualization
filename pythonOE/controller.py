from model import Model
from datetime import datetime
from pathlib import Path
import threading
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import signal 



class Controller: 

    def __init__(self):

        
        self.selected_folder =  None
        self.is_running = False
        self.event_type = ""
        self.model = None

        self.nbr_events = 4
        self.nbr_event_received = 0
        self.events= dict()
        self.special_events= dict(Average=[])
        self.register_line = np.zeros(32)
        self.register_line[0] = 1
        self.event_duration = 100
        self.lc = 1
        self.hc = 200
        self.order = 4
        self.notch_freq = []
        self.denoise = False

        self.executor = ThreadPoolExecutor(max_workers=1)

    def close(self):
        self.executor.shutdown(wait=False)

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

        self.view.clear_events()
        self.model.setup_filters(self.lc,self.hc, self.order, self.notch_freq, self.denoise)

        return self.selected_folder, self.data_folder

    def setup_event_view(self, num_channel, nb_col, nb_line, col_divider, row_divider):
        self.model = Model(num_channel, nb_col, nb_line, col_divider, row_divider)
        return self.model.reset_xy(self.event_duration)

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

        def add_event_in_thread(nbr_event_received):
            self.model.add_event(info)

            if self.nbr_events != 0 and nbr_event_received >= self.nbr_events:
                self.view.stop_acquisition()

            self.events[str(info['sample_number'])] = info['sample_number']
            self.special_events["Average"].append(info['sample_number'])
            self.view.add_dropdown_option(str(info['sample_number']))

            if self.event_type == "Average":
                self.view.update_sources()
            print("finished computed event"+ str(info['sample_number']))

        self.executor.submit(add_event_in_thread, self.nbr_event_received)

    def update_psd(self, psd):
        
        def update_():
            if self.model is not None:
                for value in self.events:
                    self.model.compute_event(self.events[value], psd=psd)

            self.view.update_sources()
        self.executor.submit(update_)

    def update_nbr_events(self, new):
        self.nbr_events = new

    def update_snapshot(self, event_duration):
        self.event_duration = event_duration

        def update_():
            if self.model is not None:
                self.model.reset_xy(event_duration)
                for value in self.events:
                    self.model.compute_event(self.events[value])

            self.view.update_sources()
        self.executor.submit(update_)
    
    def update_filter(self, lc=None, hc=None, order=None, notch_freq=None, denoise=False):
        if order is not None:
            self.order = order

        if lc is not None:
            self.lc = lc 
        
        if hc is not None:
            self.hc = hc 
        
        if notch_freq is not None: 
            self.notch_freq = notch_freq

        self.denoise = denoise

        def update_():
            if self.model is None: 
                return
            try: 
                self.model.setup_filters(self.lc,self.hc, self.order, self.notch_freq, self.denoise)

                for value in self.events:
                    self.model.compute_event(self.events[value])
            except Exception as e: 
                print(str(e))
            self.view.update_sources()
        
        self.executor.submit(update_)


    def get_data_event(self, psd=False):
        
        if self.event_type in self.events:
            x = self.model.x
            y = self.model.data_event[self.events[self.event_type]]
        
        elif self.event_type in self.special_events:

            all_ts = self.special_events[self.event_type]
            
            if len(all_ts) != 0: 
                d = []
                
                for ts in all_ts: 
                    d.append(self.model.data_event[ts])

                d = np.stack(d)
                y = np.mean(d, axis=0)
                x = self.model.x

        else:
            x, y = self.model.reset_xy(self.event_duration)

        if psd: 
            x,y = self.model.compute_psd_with_hanning(y)

        return x, y


    def get_full_data(self):
        if self.model is None: 
            return False, None, None
        x, y = self.model.get_full_signal()
        return True, x, y



