import cupy as cp
import numpy as np
import time 


class Model:

    def __init__(self, num_channel, nbr_col, nbr_row, col_divider, row_divider):

        self.fs = 1953.12 #Hz
        self.event_snapshot_duration = 0.1
        self.data_event = dict()

        self.num_channel = num_channel
        self.nbr_col=nbr_col
        self.nbr_row= nbr_row
        self.col_divider=col_divider
        self.row_divider= row_divider

        self.lc = 1
        self.hc = 200
        self.order = 4
        self.data = None

    def reset_xy(self, event_duration=100):
        self.event_snapshot_duration = event_duration/1000
        self.snapshot_len = int(self.event_snapshot_duration * self.fs)
        self.x = np.arange(int(self.event_snapshot_duration * self.fs)*2)
        y = np.zeros(int(self.event_snapshot_duration * self.fs)*2)
        self.data = None
        return self.x, y 

    def read_data(self, recursive=True):
        try: 
            data = np.memmap(self.file, mode="r", dtype="int16")
            samples = data.reshape(
                    (
                        len(data) // self.num_channel,
                        self.num_channel,
                    )
            )
        except ValueError:
            if recursive:
                time.sleep(1)
                print("retry reading file.")
                
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
        while(self.data.shape[0] < (info['sample_number']+ int(self.event_snapshot_duration * self.fs))):
            self.read_data()

        channels = self.compute_event(info['sample_number'])

    def compute_event(self, event_ts):

        data_slice = self.data[event_ts - self.snapshot_len:event_ts + self.snapshot_len]
        data_slice = apply_bandpass_filter(data_slice, self.fs, lowcut=self.lc, highcut=self.hc, order=self.order)

        reshaped = data_slice.reshape((data_slice.shape[0], int(self.nbr_row/self.row_divider), self.row_divider, int(self.nbr_col/self.col_divider), self.col_divider))
        reshaped = reshaped.transpose(1, 3, 0, 2, 4).reshape((int(self.num_channel/(self.col_divider*self.row_divider)), data_slice.shape[0], self.row_divider, self.col_divider))

        meaned = np.mean(reshaped, axis=(2, 3))
        self.data_event[event_ts] = meaned.tolist()
    
    def get_full_signal(self, nrow, ncol):
        data = self.data[:, nrow, ncol]
        try: 
            data = apply_bandpass_filter(data, self.fs, lowcut=self.lc, highcut=self.hc, order=self.order)
        except Exception as error: 
            print(str(error))
            pass

        return np.arange(data.shape[0])*self.fs, data
from scipy.signal import butter, filtfilt

def butter_bandpass(lowcut, highcut, fs, order=4):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = butter(order, [low, high], btype="band")
    return b, a

def apply_bandpass_filter(data, fs, lowcut=1, highcut=200, order=4):
    b, a = butter_bandpass(lowcut, highcut, fs, order)

    filtered = filtfilt(b, a, data, axis=0)
    return filtered


def notch_filter():

    self.data_notch = np.empty(np.shape(self.data))
    heart_freq, heart_harmonics = 1.9, 10
    powerline_freq, powerline_harmonics = 72, 1
    Q=40     

    filtered_signal = self.data_band_pass[mux, ana, :]
    for i in range(1, heart_harmonics + 1):
        f0 = heart_freq * i
        if f0 >= self.sampling_frequency / 2:  # Avoid filtering above Nyquist frequency
                    reak
                    b, a = iirnotch(f0, Q, self.sampling_frequency)
                    filtered_signal = filtfilt(b, a, filtered_signal)