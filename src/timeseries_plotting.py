import numpy as np
import panel as pn
import holoviews as hv
import panel as pn
from bokeh.models import Spinner
import time
from holoviews.streams import Pipe

hv.extension('bokeh')

class TimeseriesView(pn.viewable.Viewer):
    def __init__(self, controller, nbr_col, nbr_row, update_period=1000, **params):
        super().__init__(**params)
        self.controller = controller
        self.sub_curves = []
        self.periodic_callback = None
        self.update_period = update_period  # in ms
        rolling_window = 5000*3
        self.event_drawed = []

        self.nbr_col = nbr_col
        self.nbr_row = nbr_row

        self.pipe = Pipe(data=(np.zeros((0,0)), np.zeros((0,1,1))))

        def overlay_with_events(data):
            elements = []
            x, y = data
            offset = 0  # initial vertical offset
            spacing_factor = 1.5  # how much space between traces (e.g. 10% more than previous max)

            for i, sub in enumerate(self.sub_curves):
                row = sub['spinner_row'].value
                col = sub['spinner_col'].value
                
                # Bounds checking
                if row >= y.shape[1] or col >= y.shape[2]:
                    continue
                
                if y.shape[0] == 0:
                    elements.append(
                        hv.Curve(([],[]), label=f"(R{row}, C{col})")
                        .opts(
                            axiswise=False, 
                            framewise=True,
                            line_width=2,  # Thicker lines for visibility
                        )
                    )
                    continue


                y_sub = y[:, row, col]

                if self.PSD.value: 
                    x, y_sub = self.controller.model.compute_psd_with_hanning(y_sub)
                    
                y_sub = y_sub + offset

                curve = hv.Curve((x,  y_sub), label=f"(R{row}, C{col})").opts(
                        axiswise=False, 
                        framewise=True,
                        line_width=2,  # Thicker lines for visibility
                    )
                if self.PSD.value: 
                    curve = curve.redim.range(x=(0,200))

                elements.append(curve)

                offset = np.max(y_sub) * spacing_factor


            ov = hv.Overlay(elements).opts(
                yaxis='left',
                show_grid=True,
                responsive=True,  # Changed to True for responsiveness
                show_legend=True,
                legend_position='top_right',  # Better legend placement
                legend_offset=(10, 10),
                tools=['xwheel_zoom', 'ywheel_zoom', 'xpan', 'reset'], 
                active_tools=['ywheel_zoom'],
                min_height=500,  # Fixed height for better control
                xlabel="Time (s)",
                ylabel="Amplitude",
                # Font size adjustments
                fontsize={
                    'title': 12,
                    'labels': 10,
                    'xticks': 8,
                    'yticks': 8,
                    'legend': 9
                },
                # Tick adjustments to prevent overlap
                xticks=6,
                xrotation=45,
            )
            return ov
        
        self.add_sub_button = pn.widgets.Button(
            name="+ Add signal", 
            button_type="primary"
        )
        self.add_sub_button.on_click(self.add_sub_curve)
        self.PSD = pn.widgets.Checkbox(name=f"PSD", value=False, align="center")
        self.PSD.param.watch(self.update, "value")

        self.controls = pn.Column(
            pn.Row(self.add_sub_button, self.PSD),
            sizing_mode="stretch_width"
        )
        self.add_sub_curve()

        dmap = hv.DynamicMap(
            lambda data: overlay_with_events(data),
            streams=[self.pipe]
        )

        self.plot = dmap


        self._panel = pn.Column(
            self.controls, 
            pn.pane.HoloViews(
                self.plot, 
                sizing_mode="stretch_both",  # Better responsiveness
                min_height=400
            ),
            sizing_mode="stretch_both"
        )

    def update_grid(self,  nbr_col,  nbr_row):
        self.nbr_row = nbr_row
        self.nbr_col = nbr_col 

    def add_sub_curve(self, event=None):
        # Determine max values based on actual data dimensions
        max_row = self.nbr_row - 1 if self.nbr_row > 0 else 1000
        max_col = self.nbr_col - 1 if self.nbr_col > 0 else 1000
        
        # Row/col spinners with proper bounds
        spinner_row = pn.widgets.Spinner(
            name="Row", 
            start=0, 
            end=max_row, 
            step=1, 
            value=min(len(self.sub_curves), max_row),  # Auto-increment default value
            align="center"
        )
        spinner_col = pn.widgets.Spinner(
            name="Column", 
            start=0, 
            end=max_col, 
            step=1, 
            value=0,
            align="center"
        )
        
        remove_btn = pn.widgets.Button(
            name="✕", 
            button_type="danger",
            align="center"
        )
        
        # Watch for changes
        spinner_col.param.watch(self.update_column, "value")
        spinner_row.param.watch(self.update_row, "value")

        c = pn.Row(
            spinner_row, 
            spinner_col, 
            remove_btn,
            sizing_mode="stretch_width"
        )

        # Store reference to the row component in sub_curves
        sub_entry = {
            'spinner_row': spinner_row,
            'spinner_col': spinner_col,
            'remove_btn': remove_btn,
            'row_component': c,  # Store reference for easier removal
            'index': len(self.sub_curves)  # Track original index
        }

        # Remove callback
        def remove_callback(ev):
            # Remove the visual component
            if c in self.controls:
                self.controls.remove(c)
            
            # Remove from sub_curves list
            if sub_entry in self.sub_curves:
                self.sub_curves.remove(sub_entry)
            
            # Update labels for remaining sub-curves
            for i, sub in enumerate(self.sub_curves):
                if 'row_component' in sub and len(sub['row_component']) > 0:
                    # Update the label
                    sub['row_component'][0].object = f""
                    sub['index'] = i
            
            # Trigger update
            self.update()

        remove_btn.on_click(remove_callback)

        # Add to list and controls
        self.sub_curves.append(sub_entry)
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

    def update(self, value=None):
        x_data, y_data = self.controller.get_full_data(psd=bool(self.PSD.value))

        if x_data is None:
            return
        
        self.pipe.send((x_data, y_data))

    def start_streaming(self):
        if self.periodic_callback is None:
            self.periodic_callback = pn.state.add_periodic_callback(self.update, period=self.update_period)

    def stop_streaming(self):
        if self.periodic_callback is not None:
            self.periodic_callback.stop()
            self.periodic_callback = None