import numpy as np
import panel as pn
import holoviews as hv
import panel as pn
from bokeh.models import ColumnDataSource, Spinner, Span
from bokeh.plotting import figure
import threading
import time
from holoviews.streams import Pipe

pn.extension('bokeh')
hv.extension('bokeh')

class TimeseriesView(pn.viewable.Viewer):
    def __init__(self, controller, rolling_window=5000, update_period=50, **params):
        super().__init__(**params)
        self.controller = controller
        self.row = 0
        self.col = 0
        self.rolling_window = rolling_window
        self.update_period = update_period  # in ms
        self.event_drawed = []
        self.ts_x = 0

        self.pipe = Pipe(data=([], []))
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

        # --- Periodic callback for streaming ---
        pn.state.add_periodic_callback(self.update, period=self.update_period)

    def __panel__(self):
        return self._panel

    # ------------------------------------------------
    # Widget callbacks
    # ------------------------------------------------
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

    # ------------------------------------------------
    # Data streaming callback
    # ------------------------------------------------
    def update(self):
        valid, x_data, y_data = self.controller.get_full_data(self.row, self.col)
        if not valid:
            return

        self.pipe.send({'x': x_data, 'y': y_data})

        for ts in self.controller.events.values():
            if ts not in self.event_drawed:
                self.event_drawed.append(ts)
                vloc = ts * self.controller.model.fs

                span = Span(location=vloc, dimension='height', line_color='red', line_width=0.5, line_dash='dashed')
                self._panel[1].object = self.plot*span


