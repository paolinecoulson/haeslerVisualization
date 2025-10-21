import numpy as np
import panel as pn
import holoviews as hv
import panel as pn
from bokeh.models import ColumnDataSource, Spinner, Span
from bokeh.plotting import figure
import threading
import time
from holoviews.streams import Buffer
import pandas as pd
pn.extension('bokeh')
hv.extension('bokeh')

class TimeseriesView(pn.viewable.Viewer):
    def __init__(self, controller, update_period=2000, **params):
        super().__init__(**params)
        self.controller = controller
        self.row = 0
        self.col = 0
        self.periodic_callback= None
        self.update_period = update_period  # in ms
        rolling_window = 5000*3
        self.event_drawed = []
        self.ts_x = 0
         
        self.pipe = Buffer(data=pd.DataFrame({'x': [], 'y': []}, columns=['x', 'y']), length=rolling_window*3)

        def overlay_with_events(x, y):
            elements = [hv.Curve((x, y))]
            for ts in self.controller.events.values():
                vloc = ts * self.controller.model.fs
                elements.append(hv.VLine(vloc).opts(line_color='red', line_width=1, line_dash='dashed'))
            return hv.Overlay(elements)


        dmap = hv.DynamicMap(hv.Curve, streams=[self.pipe]).opts(
            framewise=True,  
            axiswise=True,  
            tools=['xwheel_zoom', 'xpan'],
            active_tools=['xwheel_zoom'],
            show_grid=True
        )

        self.plot = dmap

        # --- Widgets ---
        self.spinner_column = pn.widgets.Spinner(
            name="Column channel number",
            start=0, end=1000, step=1, value=self.col
        )
        self.spinner_row = pn.widgets.Spinner(
            name="Row channel number",
            start=0, end=1000, step=1, value=self.row
        )

        self.spinner_column.param.watch(self.update_column, "value")
        self.spinner_row.param.watch(self.update_row, "value")

        # --- Layout ---
        controls = pn.Row(self.spinner_column, self.spinner_row, sizing_mode="stretch_width")
        self._panel = pn.Column(controls, pn.pane.HoloViews(self.plot, sizing_mode="stretch_width"))


    def __panel__(self):
        return self._panel

    def update_column(self, event):
        new = event.new
        if self.controller.is_running and new > self.controller.model.ncol:
            self.spinner_column.value = event.old
            return
        self.col = new

    def update_row(self, event):
        new = event.new
        if self.controller.is_running and new > self.controller.model.nrow:
            self.spinner_row.value = event.old
            return
        self.row = new

    def update(self):
        valid, x_data, y_data = self.controller.get_full_data(self.row, self.col)

        if not valid:
            return
        
        self.pipe.send(pd.DataFrame({'x': x_data, 'y': y_data}, columns=['x', 'y']))

    def start_streaming(self):
        if self.periodic_callback is None:
            self.periodic_callback = pn.state.add_periodic_callback(self.update, period=self.update_period)

    def stop_streaming(self):
        if self.periodic_callback is not None:
            self.periodic_callback.stop()
            self.periodic_callback = None