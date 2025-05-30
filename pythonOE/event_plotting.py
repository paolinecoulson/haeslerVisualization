import numpy as np
from bokeh.layouts import gridplot
from bokeh.plotting import figure, curdoc, column, row
from bokeh.models import ColumnDataSource,  Dropdown, Select, Div, Button,  Spinner, Checkbox, InlineStyleSheet, Spacer, TablerIcon, Span, DataRange1d
from data_stream import stream, controller
from bokeh.document import without_document_lock
import asyncio
from functools import partial
from concurrent.futures import ThreadPoolExecutor
import tkinter as tk
from tkinter import filedialog
import threading

style = InlineStyleSheet(css="""
        :host(.box-element) {
            border: 1px solid #ccc;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 20px;
            background-color: #f9f9f9;
        }
        """)

class EventView:
    def __init__(self, controller):

        self.executor = ThreadPoolExecutor()
        self.controller = controller
        self.controller.set_view_callback(self)


        self.doc = curdoc()
        self.grid = None
        self.container = column()

        spinner_duration = Spinner(title="Event duration (ms): ", low=0, high=1000, step=10, value=100, width=150)
        spinner_duration.on_change("value", self.update_snapshot)

        self.spinner_nbr_events = Spinner(title="Number of events to record : ", low=0, high=10, step=1, value=4, width=160)
        self.spinner_nbr_events.on_change("value", self.update_spinner_nbr_events)

        self.dropdown = Select(title = "Event type:", value = self.controller.event_type, options=[self.controller.event_type])
        self.dropdown.on_change("value", self.update_type_event)
        
        self.path_display = Div(text="Data acquisition path: <i>None</i>", width=300)
        self.folder_display = Div(text="Data acquisition folder: <i>None</i>", width=200)

        self.select_folder_btn = Button(label="Select Folder", icon = TablerIcon(icon_name="folder-search", size=16), button_type="primary")
        
        self.start_btn = Button(label="", icon = TablerIcon(icon_name="player-play", size=16), button_type="success")
        self.stop_btn = Button(label="", icon = TablerIcon(icon_name="player-stop", size=16), button_type="danger")

        self.start_btn.on_click(self.start_acquisition)
        self.stop_btn.on_click(self.stop_acquistion)

        self.selected_folder = ""
        self.select_folder_btn.on_click(self.select_folder)

        param_layout = row(self.select_folder_btn, self.start_btn, self.stop_btn)
        file_layout = row(self.path_display, self.folder_display)
        
        
        filter_param_layout = self.setup_filter_param()
        probe_param_layout = self.setup_probe_param()
        event_param_layout = self.setup_event_param()

        hidden_param_layout = row(probe_param_layout,  Spacer(width=10), filter_param_layout, Spacer(width=10),  event_param_layout)
        layout = column(row(column(param_layout, file_layout,  stylesheets = [style], css_classes = ['box-element']), Spacer(width=10),
                        row(self.dropdown, spinner_duration, self.spinner_nbr_events,  stylesheets = [style], css_classes = ['box-element'])),
                        hidden_param_layout, 
                        )

        self.doc.add_root(layout)
        self.doc.title = "Event live plotting"

    def setup_filter_param(self):
        lowcut_spin = Spinner(title="Low cutoff frequency: ", low=0.5, high=500, step=1, value=1, width=150)
        highcut_spin = Spinner(title="High cutoff frequency: ", low=40, high=4000, step=10, value=200, width=150)
        hidden_section = row(
                    Div(text="Bandpass filter parameters :"),
                    column(lowcut_spin,  highcut_spin)
                )
        
        def update_spinner_lc(attr, old, new):
            if new < self.highcut_spin.value:
                self.controller.update_freq(lc=new)

        def update_spinner_hc(attr, old, new):
            if new > self.lowcut_spin.value:
                self.controller.update_freq(hc=new)

        lowcut_spin.on_change("value", update_spinner_lc)
        highcut_spin.on_change("value", update_spinner_hc)
                
        hidden_section.visible = False  
        return self.setup_hidden_param(hidden_section, "filter")

    def setup_probe_param(self):
        self.nrows = 32
        self.ncols = 96
        self.row_divider = 4
        self.col_divider = 4

        ch_col_spin = Spinner(title="Column: ", low=1, high=100, step=1, value=self.ncols, width=100)
        ch_row_spin = Spinner(title="Row   : ", low=1, high=100, step=1, value=self.nrows, width=100)
        
        dis_col_spin = Spinner(title="       ", low=1, high=100, step=1, value=self.col_divider, width=100)
        dis_row_spin = Spinner(title="       ", low=1, high=100, step=1, value=self.row_divider, width=100)
        
        self.load_button = Button(label=f"Load probe view", button_type="primary")

        hidden_section = column(

                    row(Div(text="Probe   :"), ch_col_spin,  ch_row_spin),
                    row(Div(text="Display :"), dis_col_spin,  dis_row_spin),
                    self.load_button
                )
        
        def update_ch_row(attr, old, new):
            self.nrows = new
            if(self.nrows % self.row_divider != 0):
                dis_row_spin.value = self.nrows

        def update_ch_col(attr, old, new):
            self.ncols = new
            if(self.ncols % self.col_divider != 0):
                dis_col_spin.value = self.ncols

        def update_dis_col_spin(attr, old, new):
            self.col_divider = new
            if(self.ncols % self.col_divider != 0):
                dis_col_spin.value = old

        def update_dis_row_spin(attr, old, new):
            self.row_divider = new
            if(self.nrows % self.row_divider != 0):
                dis_row_spin.value = old

        def create_view_button():
            self.controller.setup_event_view(self.ncols*self.nrows, self.ncols, self.nrows, self.col_divider, self.row_divider)

            self.load_button.icon  = TablerIcon(icon_name="loader", size=16)
            self.load_button.label = 'Loading graphs - can take long time.'
            hidden_section.disabled = True 

            if self.grid is not None: 
                self.grid.destroy()
                self.container.children.remove(self.grid)

            def load_in_thread():
                x, y = self.controller.model.reset_xy(event_duration=100)
                self.sources = [ColumnDataSource(data=dict(x=x, y=y)) for _ in range(int(self.nrows*self.ncols/(self.col_divider*self.row_divider)))]
                self.setup_event_view()

                def reactivate_button():
                    self.load_button.icon  =  TablerIcon(icon_name="check", size=16)
                    self.load_button.label = 'Load probe view'
                    hidden_section.disabled = False
                
                self.doc.add_next_tick_callback(reactivate_button)

            threading.Thread(target = load_in_thread).start()

        ch_col_spin.on_change("value", update_ch_col)
        ch_row_spin.on_change("value", update_ch_row)
        dis_col_spin.on_change("value", update_dis_col_spin)
        dis_row_spin.on_change("value", update_dis_row_spin)

        self.load_button.on_click(create_view_button)
                
        hidden_section.visible = True  
        return self.setup_hidden_param(hidden_section, "probe")

    def setup_event_param(self):
        checkboxes = [Checkbox(label=f"Line {i}", active=False, width=60) for i in range(32)]
        def checkbox_callback(attr, old, new, idx):
            if new:
                self.controller.add_event_line(idx)
            else: 
                self.controller.remove_event_line(idx)

        for i, cb in enumerate(checkboxes):
            if i == 8:
                cb.active = True
                
            cb.on_change("active", lambda attr, old, new, i=i: checkbox_callback(attr, old, new, i))



        rows = [checkboxes[i::4] for i in range(4)]
        checkbox_grid = gridplot(rows)

        hidden_section = column(
                    Div(text="Select event trigger:"),
                    checkbox_grid
                )
                
        hidden_section.visible = False  # Start hidden
        return self.setup_hidden_param(hidden_section, "events")

    def setup_hidden_param(self, hidden_section, label):
        icon_open = TablerIcon(icon_name="toggle-right", size=16)
        icon_close = TablerIcon(icon_name="toggle-left", size=16)

        toggle_button = Button(label="", button_type="primary")
        toggle_button.label = f"Hide {label} Settings" if hidden_section.visible else f"Show {label} Settings"
        toggle_button.icon = icon_open if hidden_section.visible else icon_close
        def toggle_section():
            hidden_section.visible = not hidden_section.visible
            toggle_button.label = f"Hide {label} Settings" if hidden_section.visible else f"Show {label} Settings"
            toggle_button.icon = icon_open if hidden_section.visible else icon_close

        toggle_button.on_click(toggle_section)
        
        return column(toggle_button, hidden_section, stylesheets = [style], css_classes = ['box-element'])


    def setup_event_view(self):


        self.vline = []
        plots =[]

        shared_x_range = DataRange1d()
        nbr_col_display = int(self.ncols/self.col_divider)
        nbr_row_display = int(self.nrows/self.row_divider)
        for i in range(0, int(nbr_row_display*nbr_col_display)):

            plot = figure(
                height=150,
                width=150,
                tools="pan,wheel_zoom,reset",
                toolbar_location=None,
                title="C " + str((i%nbr_col_display)*self.col_divider) + "-" 
                        + str((i%nbr_col_display+1)*self.col_divider-1) + "\nR " 
                        + str(int(i/nbr_col_display)*self.row_divider)+ "-" 
                        +str(int(i/nbr_col_display+1)*self.row_divider-1) ,
                output_backend="webgl",
                x_range=shared_x_range
            )
            plot.line(x="x", y="y", source=self.sources[i])
            vline = Span(location=self.sources[0].data["x"][-1]/2, dimension='height', line_color='red', line_width=0.5, line_dash='dashed')
            plot.add_layout(vline)
            self.vline.append(vline)
            plot.xaxis.visible = False
            plot.yaxis.visible = False
            plots.append(plot)

        def update_view():
            self.grid = gridplot(plots, ncols=nbr_col_display)
            self.container = column(self.grid)
            self.doc.add_root(self.container)
        
        self.doc.add_next_tick_callback(update_view)

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
        self.load_button.disabled = True

    def stop_acquistion_from_thread(self): 
        self.doc.add_next_tick_callback(self.stop_acquistion)

    def stop_acquistion(self):
        stream.stop_acquistion()
        self.start_btn.disabled = False 
        self.select_folder_btn.disabled = False
        self.spinner_nbr_events.disabled = False
        self.load_button.disabled = False
        
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
        if len(x) != len(source.data["x"]):

            for vline in self.vline:
                vline.location = len(x)/2

        source.data = {"x": x, "y": y}

ev = EventView(controller)