import numpy as np
import time 
from scipy.signal import butter, filtfilt, tf2sos, sosfiltfilt, iirnotch

class Model:

    def __init__(self, num_channel, nbr_col, nbr_row, col_divider, row_divider):

        self.fs = 1953.12 #Hz
        self.data_event = dict()

        self.num_channel = num_channel
        self.nbr_col=nbr_col
        self.nbr_row= nbr_row
        self.col_divider=col_divider
        self.row_divider= row_divider

        self.data = None
        self.data_path = None

    def reset_xy(self, event_duration=100):

        half_snapshot_sec = event_duration / 1000.0
        self.snapshot_len = int(half_snapshot_sec * self.fs)

        n_samples = 2 * self.snapshot_len
        self.x = np.linspace(-event_duration, event_duration, n_samples, endpoint=True)

        y = np.ones(n_samples)
        y = np.tile(y, (int(self.nbr_col/self.col_divider)*int(self.nbr_row/self.row_divider), 1))
        return self.x, y


    def read_data(self, recursive=True):
        if self.data_path is None:
            return 

        try:
            if self.file is None:
                self.file = next(self.data_path.rglob("continuous.*"))

            data = np.memmap(self.file, mode="r", dtype="int16")
            samples = data.reshape(
                    (
                        len(data) // self.num_channel,
                        self.num_channel,
                    )
            )
        except ValueError as error:
            if recursive:
                time.sleep(1)
                print("retry reading file. " + str(error))
                
                self.read_data()
            return

        self.data = samples.reshape(-1, self.nbr_row, self.nbr_col)

    def get_full_signal(self, channel):
        return self.read_data()[:, channel]

    def get_event(self, ts):
        return self.data_event[ts]

    def add_event(self, info):
        print("event " + str(info['sample_number']))

        self.read_data()
        while(self.data.shape[0] < (info['sample_number']+ int(self.snapshot_len))):
            self.read_data()

        channels = self.compute_event(info['sample_number'])

    def compute_event(self, event_ts):

        data = self.data[event_ts - self.snapshot_len:event_ts + self.snapshot_len]
        try:     
            data = sosfiltfilt(self.sos_all, data, axis=0)
        except Exception as error: 
            print(str(error))
            pass
        reshaped = data.reshape((data.shape[0], int(self.nbr_row/self.row_divider), self.row_divider, int(self.nbr_col/self.col_divider), self.col_divider))
        reshaped = reshaped.transpose(1, 3, 0, 2, 4).reshape((int(self.num_channel/(self.col_divider*self.row_divider)), data.shape[0], self.row_divider, self.col_divider))

        meaned = np.mean(reshaped, axis=(2, 3))
        meaned = (meaned) / (meaned.std(axis=1, keepdims=True))
        self.data_event[event_ts] = meaned
    
    def get_full_signal(self, nrow, ncol):
        data = self.data[:, nrow, ncol]
        try: 
            data_filt = sosfiltfilt(self.sos_all, data, axis=0)
        except Exception as error: 
            print(str(error))
            pass

        return np.arange(data_filt.shape[0])*self.fs, data_filt


    def setup_filters( self, lowcut, highcut, order, notch_freq):
        sos = butter(order, [lowcut, highcut], btype='bandpass', fs=self.fs, output='sos')
        sos_notches = []
    
        for notch in notch_freq:
            for  i in range(0, notch[1]+1):
                if notch[0]*(i+1) < self.fs/2:
                    b, a = iirnotch(w0=notch[0]*(i+1), Q=40, fs=self.fs) 
                    sos_notches.append(tf2sos(b, a))
        
        self.sos_all = np.vstack(sos_notches+[sos])