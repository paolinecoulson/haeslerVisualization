"""
Panel + HoloViews port of your Bokeh EventView.

Start with `panel serve event_panel_app.py`.
"""
from holoviews.streams import Pipe
import holoviews as hv
import json
import base64
import threading
from functools import partial

import os
import numpy as np
import panel as pn
import holoviews as hv

# ensure bokeh backend
hv.extension("plotly")
pn.extension('plotly')
pn.extension(nthreads=5)

pn.extension(sizing_mode="stretch_width")

from data_stream import stream, controller 


def dict_to_bytes(d: dict) -> bytes:
    return json.dumps(d, indent=2).encode("utf-8")


class EventViewPanel(pn.viewable.Viewer):
    def __init__(self, controller):
        self.controller = controller
        self.controller.set_view_callback(self)  # keep same contract

        # Internal state (kept similar to original)
        self.nrows = 32
        self.ncols = 96
        self.row_divider = 4
        self.col_divider = 4
        self.sources = None      # will hold arrays of (x,y) data
        self.hv_layout = None    # holoviews Layout of plots
        self.vline_pos = None    # position for vertical line if needed

        # ---------------------------
        # Widgets
        # ---------------------------
        # Spinners / numeric inputs
        self.spinner_duration = pn.widgets.IntInput(
            name="Event duration (ms)", value=100, step=10, start=0, end=1000, align="end"
        )
        self.spinner_duration.param.watch(self._on_duration_change, "value")

        self.spinner_nbr_events = pn.widgets.IntInput(
            name="Number of events to record", value=4, step=1, start=0, end=10,  align='end'
        )
        self.spinner_nbr_events.param.watch(self._on_nbr_events_change, "value")

        # Event type dropdown
        self.dropdown = pn.widgets.Select(name="Event type", options=[controller.event_type], value=controller.event_type, align="end")
        self.dropdown.param.watch(self._on_event_type_change, "value")

        # Path displays
        self.path_display = pn.widgets.StaticText(name="Data acquisition path", value="None")
        self.folder_display = pn.widgets.StaticText(name="Data acquisition folder", value="None")

        # Buttons
        self.select_folder_btn = pn.widgets.Button(name="Select Folder", button_type="primary", align='center')
        self.start_btn = pn.widgets.Button(name="Start", button_type="success", icon="play",  align='end')
        self.start_btn.disabled = True
        self.stop_btn = pn.widgets.Button(name="Stop", button_type="danger", icon="stop", align='end')

        self.select_folder_btn.on_click(self.select_folder)
        self.select_folder_btn.disabled = True

        self.start_btn.on_click(self.start_acquisition)
        self.stop_btn.on_click(self.stop_acquisition)

        # Config file widgets
        self.file_input = pn.widgets.FileInput(accept=".json", align="center", margin=0)
        self.file_input.param.watch(self._on_config_file_uploaded, "value")

        # FileDownload that uses a callback to get bytes
        self.download_btn = pn.widgets.FileDownload(callback=self._get_config_bytes, filename="config.json", button_type="primary", align='center')

        # Filter parameters
        self.lowcut_spin = pn.widgets.FloatInput(name="Low cutoff frequency", value=1, step=1, start=0.5, end=500)
        self.highcut_spin = pn.widgets.IntInput(name="High cutoff frequency", value=200, step=10, start=40, end=4000)
        self.order_spin = pn.widgets.IntInput(name="Order", value=4, step=1, start=1, end=100)
        self.filter_apply_btn = pn.widgets.Button(name="Apply filters", button_type="primary")
        self.filter_apply_btn.on_click(self._apply_filters)

        # Notch filters dynamic area
        self.notch_layout = pn.Column()
        self.add_notch_btn = pn.widgets.Button(name="Add notch filter", button_type="primary")
        self.clear_notch_btn = pn.widgets.Button(name="Clear notch filters", button_type="danger")
        self.add_notch_btn.on_click(self._add_notch_filter)
        self.clear_notch_btn.on_click(self._clear_notch_filters)
        self.notch_widgets = []  # list of (freq_spinner, harmonic_spinner)

        # Probe parameters
        self.ch_col_spin = pn.widgets.IntInput(name="Probe Columns", value=self.ncols, step=1, start=1, end=100)
        self.ch_row_spin = pn.widgets.IntInput(name="Probe Rows", value=self.nrows, step=1, start=1, end=100)
        self.dis_col_spin = pn.widgets.IntInput(name="Divider column", value=self.col_divider, step=1, start=1, end=100)
        self.dis_row_spin = pn.widgets.IntInput(name="Divider row", value=self.row_divider, step=1, start=1, end=100)
        self.load_button = pn.widgets.Button(name="Load probe view", button_type="primary")
        self.load_button.on_click(self._create_view_button)

        # watchers to keep internal variables in sync
        self.ch_col_spin.param.watch(self._on_ch_col_change, "value")
        self.ch_row_spin.param.watch(self._on_ch_row_change, "value")
        self.dis_col_spin.param.watch(self._on_dis_col_change, "value")
        self.dis_row_spin.param.watch(self._on_dis_row_change, "value")

        # Events checkboxes grid (32 checkboxes)
        self.event_checkboxes = [pn.widgets.Checkbox(name=f"Line {i}", value=(i==0)) for i in range(32)]
        for i, cb in enumerate(self.event_checkboxes):
            cb.param.watch(partial(self._checkbox_callback, idx=i), "value")

        # Event create / average widget
        self.event_name_text = pn.widgets.TextInput(name="Name your new average event", placeholder="Event name")
        self.add_event_btn = pn.widgets.Button(name="Add new event", button_type="primary")
        self.add_event_btn.on_click(self._add_event_group)
        self.events_section = pn.Column()  # will hold checkboxes for created event groups

        # For created event groups we still track checkboxes like in original code
        self.created_event_checkboxes = []  # list of pn.widgets.Checkbox added to events_section


        # ---------------------------
        # Layouts
        # ---------------------------
        # Build filter/probe/event panels (hidden toggles can be simulated by revealers)
        self.filter_panel = pn.Card(
            pn.Column(
                pn.pane.Markdown("**Bandpass filter parameters**"),
                pn.Row(self.lowcut_spin, self.highcut_spin),
                pn.Row(pn.Spacer(width=100),self.order_spin,pn.Spacer(width=100)),
                pn.Row(self.add_notch_btn, self.clear_notch_btn),
                self.notch_layout,
                self.filter_apply_btn,
            ),
            title="Filter",
            collapsible=True,
            collapsed=True,
            sizing_mode="stretch_width",
        )

        self.probe_panel = pn.Card(
            pn.Column(
                pn.Row(pn.pane.Markdown("Probe:"), self.ch_col_spin, self.ch_row_spin),
                pn.Row(pn.pane.Markdown("Display:"), self.dis_col_spin, self.dis_row_spin),
                self.load_button,
            ),
            title="Probe",
            collapsible=True,
            collapsed=False,
            sizing_mode="stretch_width",
        )

        self.event_panel = pn.Card(
            pn.Column(
                pn.pane.Markdown("Select event trigger:"),
                pn.GridBox(*self.event_checkboxes, ncols=4, sizing_mode="stretch_width"),
            ),
            title="Event Triggers",
            collapsible=True,
            collapsed=True,
            sizing_mode="stretch_width",
        )

        add_event_panel = pn.Card(self.event_name_text, self.add_event_btn, self.events_section, title="Create new events",  sizing_mode="stretch_width")

        loading_controls =pn.Column(pn.Row(self.select_folder_btn, pn.Column(self.path_display,self.folder_display, align='center')),
                          pn.Row(pn.widgets.StaticText(name="Configuration", value="", margin=0, align='center'), self.file_input, self.download_btn), 
                          pn.Row(self.start_btn, self.stop_btn, self.spinner_nbr_events),
                          sizing_mode="stretch_width")

        self.plot_area = pn.Column(pn.widgets.StaticText(name="", value="No probe view loaded."))

        self.layout = pn.template.FastListTemplate(
                    sidebar=[self.probe_panel, self.filter_panel, self.event_panel, add_event_panel], 
                    sidebar_width = 400,
                    main=[loading_controls, pn.Row(self.dropdown, self.spinner_duration), self.plot_area], 
                    title = "NeuroLayer real-time visualization")

    def __panel__(self):
        return self.layout 

    # ---------------------------
    # Config helpers
    # ---------------------------
    def get_config_param(self):
        cfg = {}
        cfg["save path"] = getattr(self.controller, "selected_folder", "")
        cfg["nbr event to record"] = self.spinner_nbr_events.value
        cfg["event duration"] = self.spinner_duration.value
        cfg["filter setting"] = {
            "low frequency band": self.lowcut_spin.value,
            "high frequency band": self.highcut_spin.value,
            "order": self.order_spin.value,
            "notch filter": [{"frequency": w[0].value, "harmonic": w[1].value} for w in self.notch_widgets],
        }
        if getattr(self.controller, "model", None) is not None:
            m = self.controller.model
            cfg["probe setting"] = {
                "probe column": m.nbr_col if hasattr(m, "nbr_col") else self.ncols,
                "probe row": m.nbr_row if hasattr(m, "nbr_row") else self.nrows,
                "display divider column": m.col_divider if hasattr(m, "col_divider") else self.col_divider,
                "display divider row": m.row_divider if hasattr(m, "row_divider") else self.row_divider,
            }
        cfg["event trigger setting"] = [cb.value for cb in self.event_checkboxes]
        # special events
        if hasattr(self.controller, "special_events"):
            cfg["special_events"] = self.controller.special_events
        return cfg

    def _get_config_bytes(self):
        return dict_to_bytes(self.get_config_param())

    def _on_config_file_uploaded(self, event):
        """FileInput returns a base64-encoded bytes string in event.new"""
        val = event.new
        if not val:
            return
        try:
            b = base64.b64decode(val)
            cfg = json.loads(b)
            self.set_config_param(cfg)
        except Exception as e:
            print("Failed to load config:", e)

    def set_config_param(self, config):
        # mirror logic from original set_config_param
        if "save path" in config:
            self.controller.selected_folder = config["save path"]
            self.path_display.value = config['save path']
        if "nbr event to record" in config:
            self.spinner_nbr_events.value = config["nbr event to record"]
        if "event duration" in config:
            self.spinner_duration.value = config["event duration"]
        if "probe setting" in config:
            ps = config["probe setting"]
            # try to set widgets (guard for missing keys)
            self.ch_col_spin.value = ps.get("probe column", self.ch_col_spin.value)
            self.ch_row_spin.value = ps.get("probe row", self.ch_row_spin.value)
            self.dis_col_spin.value = ps.get("display divider column", self.dis_col_spin.value)
            self.dis_row_spin.value = ps.get("display divider row", self.dis_row_spin.value)
        if "filter setting" in config:
            fs = config["filter setting"]
            self.lowcut_spin.value = fs.get("low frequency band", self.lowcut_spin.value)
            self.highcut_spin.value = fs.get("high frequency band", self.highcut_spin.value)
            self.order_spin.value = fs.get("order", self.order_spin.value)
            # notches
            if "notch filter" in fs:
                self._clear_notch_filters()
                for nf in fs["notch filter"]:
                    self._add_notch_filter(freq=nf.get("frequency", 0), harmonic=nf.get("harmonic", 0))
        if "event trigger setting" in config:
            ets = config["event trigger setting"]
            for i, val in enumerate(ets):
                if i < len(self.event_checkboxes):
                    self.event_checkboxes[i].value = bool(val)
        if "special_events" in config:
            # add created events into controller and event UI
            for name, idxs in config["special_events"].items():
                self.controller.special_events[name] = idxs
                self._add_dropdown_option(name)
    # ---------------------------
    # Filter / Notch helpers
    # ---------------------------
    def _add_notch_filter(self, event=None, freq=0, harmonic=0):
        freq_spin = pn.widgets.Spinner(name="Notch frequency", value=freq, step=1, start=0, end=1000, width=150)
        harm_spin = pn.widgets.Spinner(name="Harmonic", value=harmonic, step=1, start=0, end=10, width=150)
        row = pn.Row(freq_spin, harm_spin, sizing_mode="fixed")
        self.notch_layout.append(row)
        self.notch_widgets.append((freq_spin, harm_spin))

    def _clear_notch_filters(self, event=None):
        self.notch_layout.clear()
        self.notch_widgets.clear()

    def _apply_filters(self, event=None):
        notch_filter = [(w[0].value, w[1].value) for w in self.notch_widgets]
        self.controller.update_freq(self.lowcut_spin.value, self.highcut_spin.value, self.order_spin.value, notch_filter)

    # ---------------------------
    # Probe / View helpers
    # ---------------------------
    def _on_ch_col_change(self, event):
        self.ncols = event.new

    def _on_ch_row_change(self, event):
        self.nrows = event.new

    def _on_dis_col_change(self, event):
        self.col_divider = event.new

    def _on_dis_row_change(self, event):
        self.row_divider = event.new
        
    def _create_view_button(self, event=None):
        self.load_button.name = "Loading graphs..."
        self.load_button.disabled = True
        

        nbr_col_display = int(self.ncols / self.col_divider)
        nbr_row_display = int(self.nrows / self.row_divider)
        nplots = nbr_col_display * nbr_row_display

        self.controller.setup_event_view(self.ncols*self.nrows, self.ncols, self.nrows, self.col_divider, self.row_divider)
        self.select_folder_btn.disabled = False
        # Pre-allocate empty curves
        self.pipes = []
        hv_plots = []
        x = np.arange(self.spinner_duration.value)  # or whatever length you want
        y = np.zeros_like(x)
        self.vline_pos = len(x) / 2

        def create_plots():
            for i in range(nplots):
                # start with zeros (or empty list)

                pipe = Pipe(data=(x, y))
                self.pipes.append(pipe)

                dmap = hv.DynamicMap(hv.Curve, streams=[pipe]).opts(
                                                                    padding=(0, 0),
                                                                    xaxis='bare',  
                                                                    yaxis='bare',   
                                                                    show_grid=False,
                                                                    show_legend=False,
                                                                    responsive=False,
                                                                )
            
                hv_plots.append((dmap * hv.VLine(self.vline_pos)).opts(show_legend=False))

            layout = hv.Layout(hv_plots).cols(nbr_col_display)
            self.hv_layout = pn.pane.HoloViews(layout)
            self.plot_area.clear()
            self.plot_area.append(self.hv_layout)

            self.load_button.name = "Load probe view"
            self.load_button.disabled = False

            if self.controller.model.data_path:
                self.start_btn.disabled = False

        thread = threading.Thread(target=create_plots, daemon=True)
        thread.start()

    # ---------------------------
    # Event controls
    # ---------------------------

    def _checkbox_callback(self, event, idx):
        # event.new is boolean value
        if event.new:
            self.controller.add_event_line(idx)
        else:
            self.controller.remove_event_line(idx)


    def _add_event_group(self, event=None):
        name = self.event_name_text.value.strip()
        if name == "":
            return
        # gather currently active checkboxes
        selected = [i for i, cb in enumerate(self.event_checkboxes) if cb.value]
        if not selected:
            return
        # register with controller
        if not hasattr(self.controller, "special_events"):
            self.controller.special_events = {}
        self.controller.special_events[name] = selected
        self._add_dropdown_option(name)
        # add a checkbox to events_section so user can toggle grouping in UI
        cb = pn.widgets.Checkbox(name=name, value=False)
        self.events_section.append(cb)
        self.created_event_checkboxes.append(cb)
        self.event_name_text.value = ""

    def _add_dropdown_option(self, name):
        opts = list(self.dropdown.options) if isinstance(self.dropdown.options, (list, tuple)) else [self.dropdown.options]
        if name not in opts:
            opts.append(name)
            self.dropdown.options = opts

    def clear_events(self):
        self.dropdown.options = [self.controller.event_type]
        self.events_section.clear()
        self.created_event_checkboxes.clear()
        if hasattr(self.controller, "special_events"):
            self.controller.special_events.clear()

    # ---------------------------
    # Start/Stop acquisition
    # ---------------------------
    def start_acquisition(self, event=None):
        stream.start_acquisition()
        # controller should set data_folder attribute
        self.folder_display.value = getattr(self.controller, 'data_folder', 'None')
        self.start_btn.disabled = True
        self.select_folder_btn.disabled = True
        self.spinner_nbr_events.disabled = True
        self.load_button.disabled = True


    def stop_acquisition(self, event=None):
        stream.stop_acquisition()
        self.start_btn.disabled = False
        self.select_folder_btn.disabled = False
        self.spinner_nbr_events.disabled = False
        self.load_button.disabled = False

    def select_folder(self, event=None):
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.attributes('-topmost', True)
            root.withdraw()
            folder = filedialog.askdirectory()
            root.destroy()
        except Exception:
            folder = None

        if folder:

            self.controller.selected_folder = os.path.normpath(folder)
            self.path_display.value =  os.path.normpath(folder)
            self.start_btn.disabled = False


    def _on_duration_change(self, event):
        self.controller.update_snapshot(event.new)

    def _on_nbr_events_change(self, event):
        self.controller.update_nbr_events(event.new)

    def _on_event_type_change(self, event):
        self.controller.event_type = event.new
        self.update_sources()


    def update_sources(self):
        """Called by controller when new data is available (or by user)."""
        if self.sources is None:
            return

        x, y = self.controller.get_data_event()

        # update vline pos
        self.vline_pos = len(x) / 2

        if self.hv_layout is not None:
            for i, pipe in enumerate(self.pipes):
                pipe.send((np.array(x), np.array(y[i])))


ev = EventViewPanel(controller)

ev.servable()