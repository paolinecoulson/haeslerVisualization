from bokeh.layouts import column, row
from bokeh.models import ColumnDataSource, Spinner
from bokeh.plotting import figure, curdoc
import numpy as np
from data_stream import stream


class TimeseriesView:

    def __init__(self):
        self.source = ColumnDataSource(data=dict(x=[], y=[]))
        self.plot = figure(title="Timeseries Overview", width=1000, height=300, output_backend="webgl")
        self.plot.line("x", "y", source=self.source)

        spinner_column = Spinner(title="Column channel number: ", low=1, high=96, step=1, value=1, width=200)
        spinner_line = Spinner(title="Row channel number: ", low=1, high=32, step=1, value=1, width=200)
        self.row = 1
        self.col = 1
        self.stream = stream
        spinner_column.on_change("value", self.update_column)
        spinner_line.on_change("value", self.update_row)
        curdoc().add_root(column(row(spinner_column, spinner_line), self.plot))
        curdoc().add_periodic_callback(self.update, 1000)
        curdoc().title = "Timeseries View"

    def update_column(self, attr, old, new):
        self.col = new 

    def update_row(self, attr, old, new):
        self.row = new 

    def update(self):
        if self.stream.is_running : 
            self.stream.read_data()
            x = list(range( self.stream.data.shape[0]))
            self.source.data = {"x": x, "y": self.stream.data[:, self.row-1, self.col-1]}
        
            self.plot.x_range.start =  max(self.stream.data.shape[0]-2000, 0)
            self.plot.x_range.end = self.stream.data.shape[0]


TimeseriesView()