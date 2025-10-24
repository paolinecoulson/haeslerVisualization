import numpy as np
import panel as pn
import holoviews as hv
import panel as pn
from bokeh.models import Spinner
import time
from holoviews.streams import Pipe
pn.extension('bokeh')
hv.extension('bokeh')

class TimeseriesView(pn.viewable.Viewer):
    def __init__(self, controller, nbr_col, nbr_row, update_period=1000,**params):
        super().__init__(**params)
        self.controller = controller
        self.sub_curves= []
        self.periodic_callback= None
        self.update_period = update_period  # in ms
        rolling_window = 5000*3
        self.event_drawed = []

        self.nbr_col = nbr_col
        self.nbr_row = nbr_row

        self.pipe = Pipe(data=(np.zeros((0,0)), np.zeros((0,1,1))))

        

        def overlay_with_events(data):
            elements = []
            x,y = data

            for i, sub in enumerate(self.sub_curves):
                row = sub['spinner_row'].value
                col = sub['spinner_col'].value
                y_sub = y[:, row, col]

                elements.append(hv.Curve((x, y_sub), label=f"Sub {i} ({row},{col})").opts(axiswise=False, framewise=True))
                                

            # Event markers
            for ts in self.controller.events.values():
                vloc = ts * self.controller.model.fs
                elements.append(hv.VLine(vloc).opts(line_color='red', line_width=1, line_dash='dashed'))


            ov = hv.Overlay(elements).opts( subcoordinate_y=True, subcoordinate_scale=0.1,                    
                                            yaxis='left',
                                            show_grid=True,
                                            responsive=False,
                                            show_legend=True,
                                            tools=['xwheel_zoom','ywheel_zoom', 'xpan'], 
                                            active_tools=['ywheel_zoom'] )
            return ov
        
        self.add_sub_button = pn.widgets.Button(name="+ Add Sub-Signal", button_type="primary")
        self.add_sub_button.on_click(self.add_sub_curve)

        self.controls = pn.Column(
            self.add_sub_button,
            sizing_mode="stretch_width"
        )
        self.add_sub_curve()

        dmap = hv.DynamicMap(
                lambda data: overlay_with_events(data),
                streams=[self.pipe]  # buffer triggers the redraw
            )

        self.plot = dmap
        self._panel = pn.Column(self.controls, pn.pane.HoloViews(self.plot, sizing_mode="stretch_width"))

    def update_grid(self,  nbr_col,  nbr_row):
        self.nbr_row = nbr_row
        self.nbr_col = nbr_col 

    def add_sub_curve(self, event=None):
        # Row/col spinners
        spinner_row = pn.widgets.Spinner(
            name="Sub Row", start=0, end=1000, step=1, value=0
        )
        spinner_col = pn.widgets.Spinner(
            name="Sub Column", start=0, end=1000, step=1, value=0
        )
        remove_btn = pn.widgets.Button(name="Remove", button_type="danger")
        spinner_col.param.watch(self.update_column, "value")
        spinner_row.param.watch(self.update_row, "value")

        c = pn.Row(spinner_row, spinner_col, remove_btn)

        # Remove callback
        def remove_callback(ev):
            self.controls.remove(c)
            self.sub_curves[:] = [s for s in self.sub_curves if s['spinner_row'] != spinner_row]
            self.update()

        remove_btn.on_click(remove_callback)

        # Store sub-curve
        self.sub_curves.append({
            'spinner_row': spinner_row,
            'spinner_col': spinner_col,
            'remove_btn': remove_btn
        })

        self.controls.append(c)
        self.update()

    def __panel__(self):
        return self._panel

    def update_column(self, event):
        new = event.new
        if new > self.nbr_col:
            self.spinner_column.value = event.old
            return

        self.update()

    def update_row(self, event):
        new = event.new
        if new > self.nbr_row:
            self.spinner_row.value = event.old
            return

        self.update()

    def update(self):
        valid, x_data, y_data = self.controller.get_full_data()

        if not valid:
            return
        
        self.pipe.send((x_data, y_data))

    def start_streaming(self):
        if self.periodic_callback is None:
            self.periodic_callback = pn.state.add_periodic_callback(self.update, period=self.update_period)

    def stop_streaming(self):
        if self.periodic_callback is not None:
            self.periodic_callback.stop()
            self.periodic_callback = None