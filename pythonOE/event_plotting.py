import numpy as np
from bokeh.layouts import gridplot
from bokeh.plotting import figure, curdoc, column
from bokeh.models import ColumnDataSource,  Dropdown, Select
from data_stream import stream
from bokeh.document import without_document_lock
import asyncio
from functools import partial
from concurrent.futures import ThreadPoolExecutor


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
        for i in range(self.n_channels):
            plot = figure(
                height=150,
                width=150,
                tools="pan,wheel_zoom,reset",
                toolbar_location=None,
                title="C " + str((i%24)*4) + "-" + str((i%24+1)*4-1) + "\nL " + str(int(i/24)*4)+"-"+str(int(i/24+1)*4-1) ,
                output_backend="webgl"
            )
            plot.line(x="x", y="y", source=self.sources[i])
            plot.xaxis.visible = False
            plot.yaxis.visible = False
            plots.append(plot)

        grid = gridplot(plots, ncols=24) #96
        layout = column(self.dropdown, grid)

        self.stream = stream
        self.stream.start()

        self.x_vals = list(range(int(self.stream.event_snapshot_duration * self.stream.fs)*2))

        self.doc.add_root(layout)
        self.doc.add_periodic_callback(self.async_update_sources, 100)
        self.doc.title = "Event live plotting"


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