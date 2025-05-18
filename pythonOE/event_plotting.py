import numpy as np
from bokeh.layouts import gridplot
from bokeh.plotting import figure, curdoc, column, row
from bokeh.models import ColumnDataSource,  Dropdown, Select, Div, Button
from data_stream import stream
from bokeh.document import without_document_lock
import asyncio
from functools import partial
from concurrent.futures import ThreadPoolExecutor
import tkinter as tk
from tkinter import filedialog

class EventView:
    def __init__(self, stream):
        self.repaint = False

        self.executor = ThreadPoolExecutor()

        self.n_channels = 192
        self.doc = curdoc()

        self.sources = [ColumnDataSource(data=dict(x=[], y=[])) for _ in range(self.n_channels)]
        self.event_type = "Average"

        self.dropdown = Select(name = "Events:", value = "Average", options=["Average"])
        self.dropdown.on_change("value", self.update_type_event)
        
        plots = []
        p1 = figure(
                height=150,
                width=150,
                tools="pan,wheel_zoom,reset",
                toolbar_location=None,
                title="C 0-" + str(4-1) + "\nL 0-"+ str(4-1) ,
                output_backend="webgl",
            )

        p1.line(x="x", y="y", source=self.sources[0])
        p1.xaxis.visible = False
        p1.yaxis.visible = False

        plots =[p1]

        for i in range(1, self.n_channels):
            plot = figure(
                height=150,
                width=150,
                tools="pan,wheel_zoom,reset",
                toolbar_location=None,
                title="C " + str((i%24)*4) + "-" + str((i%24+1)*4-1) + "\nL " + str(int(i/24)*4)+"-"+str(int(i/24+1)*4-1) ,
                output_backend="webgl",
                x_range=p1.x_range
            )
            plot.line(x="x", y="y", source=self.sources[i])
            plot.xaxis.visible = False
            plot.yaxis.visible = False
            plots.append(plot)

        grid = gridplot(plots, ncols=24) #96

        self.path_display = Div(text="Data acquisition path: <i>None</i>", width=200)
        self.folder_display = Div(text="Data acquisition folder: <i>None</i>", width=200)

        self.select_folder_btn = Button(label="Select Folder", button_type="primary")
        self.start_btn = Button(label="Start", button_type="success")
        self.stop_btn = Button(label="Stop", button_type="danger")

        self.start_btn.on_click(self.start_acquisition)
        self.stop_btn.on_click(self.stop_acquistion)

        self.selected_folder = ""
        self.select_folder_btn.on_click(self.select_folder)

        param_layout = row(self.select_folder_btn, self.start_btn, self.stop_btn)
        file_layout = row(self.path_display, self.folder_display)
        layout = column(param_layout, file_layout, self.dropdown, grid)

        self.stream = stream
    
        self.x_vals = list(range(int(self.stream.event_snapshot_duration * self.stream.fs)*2))

        self.doc.add_root(layout)
        self.doc.add_periodic_callback(self.async_update_sources, 100)
        self.doc.title = "Event live plotting"


    def select_folder(self):
        root = tk.Tk()
        root.attributes('-topmost', True)
        root.withdraw()
        folder = tk.filedialog.askdirectory()  
        if folder:
            self.selected_folder = folder
            self.path_display.text = f"Selected folder: {folder}"
            self.stream.path
        else:
            self.path_display.text = "Selected folder: <i>None</i>"

    def start_acquisition(self):
        self.stream.start_acquisition()
        self.folder_display.text = f"Data acquisition folder: {self.stream.data_folder}"
        self.start_btn.disabled = True 
        self.select_folder_btn.disabled = True

    def stop_acquistion(self):
        self.stream.stop_acquistion()
        self.start_btn.disabled = False 
        self.select_folder_btn.disabled = False


    def update_type_event(self, attr, old, new):
        self.event_type = new
        self.repaint = True


    def compute_data(self, i, event_ts):
        start = event_ts - int(self.stream.event_snapshot_duration * self.stream.fs)
        end = min(event_ts + int(self.stream.event_snapshot_duration * self.stream.fs), len(self.stream.data))
        data_slice = stream.data[start:end, int((i/24)*4):int((i/24+1)*4), int((i%24)*4):int((i%24+1)*4)]
        
        return np.mean(data_slice, axis=(1, 2)).tolist()

    def update_dropdown_options(self):
        self.dropdown.options = ["Average"] + [str(ev) for ev in self.stream.events] 

    def compute_all_channels(self, event_ts):
        return [self.compute_data(i, event_ts) for i in range(self.n_channels)]
        
    # Async wrapper for non-blocking execution
    @without_document_lock
    async def async_update_sources(self):

        if self.stream.repaint or self.repaint:

            self.doc.add_next_tick_callback(self.update_dropdown_options)
            self.stream.repaint= False
            self.repaint = False

            if self.event_type == "Average":

                all_data = await asyncio.gather(*[
                    asyncio.wrap_future(self.executor.submit(self.compute_all_channels, ts))
                    for ts in self.stream.events
                ])

                averaged = np.mean(all_data, axis=0)  # shape: [n_channels][T]
                for i, source in enumerate(self.sources):
                    self.doc.add_next_tick_callback(partial(self.update_source, source, self.x_vals, averaged[i]))
            else:
                event_ts = int(self.event_type)
                one_data = await asyncio.wrap_future(self.executor.submit(self.compute_all_channels, event_ts))

                for i, source in enumerate(self.sources):
                    self.doc.add_next_tick_callback(partial(self.update_source, source,self.x_vals, one_data[i]))


    def update_source(self, source, x_vals, y_vals):
        source.data = {"x": x_vals, "y": y_vals}

ev = EventView(stream)