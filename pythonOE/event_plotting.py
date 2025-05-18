import numpy as np
from bokeh.layouts import gridplot
from bokeh.plotting import figure, curdoc, column
from bokeh.models import ColumnDataSource,  Dropdown, Select
from data_stream import stream
from bokeh.document import without_document_lock
import asyncio
from functools import partial
from concurrent.futures import ThreadPoolExecutor

global repaint
repaint = False

N_CHANNELS = 192
doc = curdoc()

sources = [ColumnDataSource(data=dict(x=[], y=[])) for _ in range(N_CHANNELS)]
global event_type 
event_type = "Average"


def update_type_event(attr, old, new):
    global event_type, repaint
    event_type = new
    repaint = True

dropdown = Select(name = "Events:", value = "Average", options=["Average"])
dropdown.on_change("value", update_type_event)


plots = []
for i in range(N_CHANNELS):
    plot = figure(
        height=150,
        width=150,
        tools="pan,wheel_zoom,reset",
        toolbar_location=None,
        title="C " + str((i%24)*4) + "-" + str((i%24+1)*4-1) + "\nL " + str(int(i/24)*4)+"-"+str(int(i/24+1)*4-1) ,
        output_backend="webgl"
    )
    plot.line(x="x", y="y", source=sources[i])
    plot.xaxis.visible = False
    plot.yaxis.visible = False
    plots.append(plot)

# Grid layout (96 columns in your case)
grid = gridplot(plots, ncols=24) #96
layout = column(dropdown, grid)

stream.start()

# Schedule source update on main thread
global x_vals
x_vals = list(range(int(stream.event_snapshot_duration * stream.fs)*2))


doc.add_root(layout)

# Executor for async tasks
executor = ThreadPoolExecutor()

# Helper: fetch and average data for one source
def compute_data(i, event_ts):
    start = event_ts - int(stream.event_snapshot_duration * stream.fs)
    end = min(event_ts + int(stream.event_snapshot_duration * stream.fs), len(stream.data))
    data_slice = stream.data[start:end, int((i/24)*4):int((i/24+1)*4), int((i%24)*4):int((i%24+1)*4)]
    
    return np.mean(data_slice, axis=(1, 2)).tolist()

def update_dropdown_options():
    dropdown.options = ["Average"] + [str(ev) for ev in stream.events] 


# Async wrapper for non-blocking execution
@without_document_lock
async def async_update_sources():
    global repaint, x_vals
    if stream.repaint or repaint:

        doc.add_next_tick_callback(update_dropdown_options)
        stream.repaint= False
        repaint = False

        def compute_all_channels(event_ts):
            return [compute_data(i, event_ts) for i in range(N_CHANNELS)]

        if event_type == "Average":
            # Gather all individual event data and average

            # Launch in background
            all_data = await asyncio.gather(*[
                asyncio.wrap_future(executor.submit(compute_all_channels, ts))
                for ts in stream.events
            ])

            # Average across all events per channel
            averaged = np.mean(all_data, axis=0)  # shape: [N_CHANNELS][T]
            for i, source in enumerate(sources):
                doc.add_next_tick_callback(partial(update_source, source, x_vals, averaged[i]))
        else:
            # Single event selected
            event_ts = int(event_type)
            one_data = await asyncio.wrap_future(executor.submit(compute_all_channels, event_ts))

            for i, source in enumerate(sources):
                doc.add_next_tick_callback(partial(update_source, source, x_vals, one_data[i]))


def update_source(source, x_vals, y_vals):
    source.data = {"x": x_vals, "y": y_vals}

doc.add_periodic_callback(async_update_sources, 100)
doc.title = "Live Ephys Data"

