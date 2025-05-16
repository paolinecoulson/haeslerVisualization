from bokeh.layouts import column
from bokeh.models import ColumnDataSource
from bokeh.plotting import figure, curdoc
import numpy as np
from data_stream import stream


source = ColumnDataSource(data=dict(x=[], y=[]))
global last_index
last_index = 0
plot = figure(title="Timeseries Overview", width=1000, height=300, output_backend="webgl")
plot.line("x", "y", source=source)

def update():
    global last_index
    stream.read_data()

    x = list(range( stream.data.shape[0]))
    source.data = {"x": x, "y": stream.data[:, 0, 0]}

    
    plot.x_range.start = last_index-1000
    plot.x_range.end = stream.data.shape[0]

    last_index = stream.data.shape[0]
        


curdoc().add_root(column(plot))
curdoc().add_periodic_callback(update, 500)
curdoc().title = "Timeseries View"
