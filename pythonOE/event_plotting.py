import numpy as np
from bokeh.layouts import gridplot
from bokeh.plotting import figure, curdoc, column, row
from bokeh.models import ColumnDataSource,  Dropdown, Select, Div, Button,  Spinner
from data_stream import stream, controller
from bokeh.document import without_document_lock
import asyncio
from functools import partial
from concurrent.futures import ThreadPoolExecutor
import tkinter as tk
from tkinter import filedialog


class EventView:
    def __init__(self, controller):

        self.executor = ThreadPoolExecutor()
        self.controller = controller
        self.controller.set_view_callback(self)

        self.n_channels = 192
        self.doc = curdoc()

        spinner_duration = Spinner(title="Event duration (ms): ", low=0, high=100, step=10, value=100, width=100)
        spinner_duration.on_change("value", self.update_snapshot)


        self.spinner_nbr_events = Spinner(title="Number of events to record : ", low=0, high=10, step=1, value=4, width=100)
        self.spinner_nbr_events.on_change("value", self.update_spinner_nbr_events)


        x, y = self.controller.model.reset_xy(event_duration=100)
        self.sources = [ColumnDataSource(data=dict(x=x, y=y)) for _ in range(self.n_channels)]
        
        self.dropdown = Select(name = "Events:", value = self.controller.event_type, options=[self.controller.event_type])
        self.dropdown.on_change("value", self.update_type_event)
        
        self.path_display = Div(text="Data acquisition path: <i>None</i>", width=200)
        self.folder_display = Div(text="Data acquisition folder: <i>None</i>", width=500)

        self.select_folder_btn = Button(label="Select Folder", button_type="primary")
        self.start_btn = Button(label="Start", button_type="success")
        self.stop_btn = Button(label="Stop", button_type="danger")

        self.start_btn.on_click(self.start_acquisition)
        self.stop_btn.on_click(self.stop_acquistion)

        self.selected_folder = ""
        self.select_folder_btn.on_click(self.select_folder)

        param_layout = row(self.select_folder_btn, self.start_btn, self.stop_btn)
        file_layout = row(self.path_display, self.folder_display, spinner_duration, self.spinner_nbr_events)
        layout = column(param_layout, file_layout, self.dropdown)

        self.doc.add_root(layout)
        self.doc.title = "Event live plotting"

        self.setup_event_view()

    def setup_event_view(self):

        self.p1 = figure(
                height=150,
                width=150,
                tools="pan,wheel_zoom,reset",
                toolbar_location=None,
                title="C 0-" + str(4-1) + "\nL 0-"+ str(4-1) ,
                output_backend="webgl",
            )

        
        renderer = self.p1.line(x="x", y="y", source=self.sources[0])
        self.renderers = [renderer]
        self.p1.xaxis.visible = False
        self.p1.yaxis.visible = False

        self.p1.x_range.start =  self.sources[0].data["x"][0]
        self.p1.x_range.end = self.sources[0].data["x"][-1]

        plots =[self.p1]

        for i in range(1, self.n_channels):
            plot = figure(
                height=150,
                width=150,
                tools="pan,wheel_zoom,reset",
                toolbar_location=None,
                title="C " + str((i%24)*4) + "-" + str((i%24+1)*4-1) + "\nL " + str(int(i/24)*4)+"-"+str(int(i/24+1)*4-1) ,
                output_backend="webgl",
                x_range=self.p1.x_range
            )
            renderer = plot.line(x="x", y="y", source=self.sources[i])
            self.renderers.append(renderer)
            plot.xaxis.visible = False
            plot.yaxis.visible = False
            plots.append(plot)

        grid = gridplot(plots, ncols=24)

        self.doc.add_root(grid)

    def update_snapshot(self, attr, old, new ):
        self.controller.update_snapshot(event_duration=new) 
    
    def update_spinner_nbr_events(self, attr, old, new):
        self.controller.update_nbr_events(new)

    def select_folder(self):
        root = tk.Tk()
        root.attributes('-topmost', True)
        root.withdraw()
        folder = tk.filedialog.askdirectory()  
        if folder:
            self.controller.selected_folder = folder
            self.path_display.text = f"Selected folder: {folder}"

        else:
            self.path_display.text = "Selected folder: <i>None</i>"

    def start_acquisition(self):
        
        stream.start_acquisition()
        self.folder_display.text = f"Data acquisition folder: {self.controller.data_folder}"
        self.start_btn.disabled = True 
        self.select_folder_btn.disabled = True
        self.spinner_nbr_events.disabled = True

    def stop_acquistion_from_thread(self): 
        self.doc.add_next_tick_callback(self.stop_acquistion)

    def stop_acquistion(self):
        stream.stop_acquistion()
        self.start_btn.disabled = False 
        self.select_folder_btn.disabled = False
        self.spinner_nbr_events.disabled = False

    def update_type_event(self, attr, old, new):
        self.controller.event_type = new
        self.update_sources()

    def add_dropdown_options(self, option):
        def update():
            if option not in self.dropdown.options:
                self.dropdown.options = self.dropdown.options + [option]
        self.doc.add_next_tick_callback(update)

    def update_sources(self):
        x, y = self.controller.get_data_event()
        for i, source in enumerate(self.sources):
            self.doc.add_next_tick_callback(partial(self.update, source, x, y[i]))
    
    def update(self, source, x, y):
        source.data = {"x": x, "y": y}
        self.p1.x_range.start =  x[0]
        self.p1.x_range.end = x[-1]

ev = EventView(controller)