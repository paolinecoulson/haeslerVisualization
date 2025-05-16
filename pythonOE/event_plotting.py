import numpy as np
from bokeh.layouts import gridplot
from bokeh.plotting import figure, curdoc, column
from bokeh.models import ColumnDataSource,  Select
from data_stream import stream

# Number of plots (channels)
N_CHANNELS = 192

# Initialize sources array
sources = [ColumnDataSource(data=dict(x=[], y=[])) for _ in range(N_CHANNELS)]


dropdown = Select(title="Events:", value = "Average", options=["Average"])
# Create plots
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

x_vals = list(range(int(stream.event_snapshot_duration * stream.fs)*2))

def update_source():

    if len(dropdown.options) > 1:

        for i, source in enumerate(sources):

                if dropdown.value == "Average":
                    d = []
                    for event_ts in dropdown.options: 
                        if event_ts == "Average":
                            continue 

                        d.append(get_data_from_one_event(int(event_ts)))
                    
                    d = np.stack(d, axis=0)
                    y_vals = np.mean(d, axis=0)
                    
                else: 
                    print(dropdown.value)
                    y_vals = get_data_from_one_event(int(dropdown.value))

                source.data = {"x": x_vals, "y": y_vals}
    
    if str(stream.last_event) not in str(dropdown.options):
        value = dropdown.value
        dropdown.options.append(str(stream.last_event))
        dropdown.value = value


def get_data_from_one_event(event_ts):

    start =event_ts- int(stream.event_snapshot_duration * stream.fs)
    end = min(event_ts + int(stream.event_snapshot_duration * stream.fs), len(stream.data))
    data_slice = stream.data[start:end, int((i/24)*4):int((i/24 +1)*4), 
                                                    int((i%24)*4):int((i%24 +1)*4)]

    return np.mean(data_slice, axis=(1, 2)).tolist()



curdoc().add_root(layout)
curdoc().add_periodic_callback(update_source, 100)
curdoc().title = "Live Ephys Data"