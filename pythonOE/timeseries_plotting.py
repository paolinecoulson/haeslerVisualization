from bokeh.layouts import column, row
from bokeh.models import ColumnDataSource, Spinner, Span
from bokeh.plotting import figure, curdoc
import numpy as np
from data_stream import controller


class TimeseriesView:

    def __init__(self):
        self.source = ColumnDataSource(data=dict(x=[], y=[]))
        self.plot = figure(title="Timeseries Overview", width=1000, height=300, output_backend="webgl")
        self.plot.line("x", "y", source=self.source)
        self.row = 0
        self.col = 0

        self.spinner_column = Spinner(title="Column channel number: ", low=0, high=1000, step=1, value=self.col, width=200)
        self.spinner_row = Spinner(title="Row channel number: ", low=0, high=1000, step=1, value=self.row, width=200)

        self.spinner_column.on_change("value", self.update_column)
        self.spinner_row.on_change("value", self.update_row)
        self.event_drawed = []

        curdoc().add_root(column(row(self.spinner_column, self.spinner_row), self.plot))
        curdoc().add_periodic_callback(self.update, 1000)
        curdoc().title = "Timeseries View"

    def update_column(self, attr, old, new):
        if controller.is_running and new > self.controller.model.ncol:
            self.spinner_column.value = old
            return
        self.col = new

    def update_row(self, attr, old, new):
        if  controller.is_running and new > self.controller.model.nrow:
            self.spinner_row.value = old
            return
        self.row = new 

    def update(self):
        valid, x, y = controller.get_full_data(self.row, self.col)
        if valid:
            for i, ts in controller.events.items(): 
                if ts not in self.event_drawed:
                    self.event_drawed.append(ts)
                    vline = Span(location=ts*controller.model.fs, dimension='height', line_color='red', line_width=0.5, line_dash='dashed')
                    self.plot.add_layout(vline)

            self.source.data = {"x":x, "y":y}

TimeseriesView()