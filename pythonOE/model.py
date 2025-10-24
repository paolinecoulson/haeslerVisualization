
import numpy as np
import time
import threading
from scipy.signal import butter, sosfiltfilt, tf2sos, iirnotch
import os
from pathlib import Path
from scipy.signal import welch, windows

class Model:
    def __init__(self, num_channel, nbr_col, nbr_row, col_divider, row_divider, max_buffer_seconds=30):
        self.fs = 1953.12  # Hz
        self.data_event = {}

        self.num_channel = num_channel
        self.nbr_col = nbr_col
        self.nbr_row = nbr_row
        self.col_divider = col_divider
        self.row_divider = row_divider

        self.data_path = None
        self.file = None

        # --- Rolling buffer settings
        self.max_buffer_seconds = max_buffer_seconds
        self.max_buffer_samples = int(max_buffer_seconds * self.fs)
        self._buffer_start_sample = 0  # absolute sample index of first in buffer
        self._offset = 0               # bytes read so far
        # Preallocate rolling buffer
        self.data = np.zeros((0, nbr_row, nbr_col), dtype=np.int16)
        self._lock = threading.Lock()  # protect shared data

        # --- Stream control
        self._stop_event = threading.Event()
        self._reader_thread = None

        # --- Filters
        self.sos_all = None
        self.denoise = False


    def start_stream(self, poll_interval=0.1):

        self._buffer_start_sample = 0  # absolute sample index of first in buffer
        self._offset = 0               # bytes read so far
        # Preallocate rolling buffer
        self.data = np.zeros((0, self.data.shape[1], self.data.shape[2]), dtype=np.int16)
        if self.data_path is None:
            raise RuntimeError("data_path not set")
        if self.file is None:
            self.file = next(self.data_path.rglob("continuous.*"))

        self._stop_event.clear()
        self._reader_thread = threading.Thread(
            target=self._watch_file, args=(poll_interval,), daemon=True
        )
        self._reader_thread.start()
        print("start reader")

    def stop_stream(self):
        self._stop_event.set()
        if self._reader_thread:
            self._reader_thread.join()
        
        print("stopping reader")

    def _watch_file(self, poll_interval):
        dtype = np.int16
        bytes_per_sample = np.dtype(dtype).itemsize * self.num_channel

        while not self._stop_event.is_set():
            try:
                size = os.path.getsize(self.file)
                available_samples = size // bytes_per_sample
                current_samples = self._offset // bytes_per_sample
                n_new = available_samples - current_samples
                if n_new > 0:
                    with open(self.file, "rb") as f:
                        f.seek(self._offset)
                        raw = np.frombuffer(
                            f.read(n_new * bytes_per_sample), dtype=dtype
                        )
                    samples = raw.reshape((n_new, self.num_channel))
                    reshaped = samples.reshape(-1, self.nbr_row, self.nbr_col)

                    with self._lock:
                        # append new data, drop oldest if needed
                        self.data = np.concatenate((self.data, reshaped), axis=0)
                        if self.data.shape[0] > self.max_buffer_samples:
                            excess = self.data.shape[0] - self.max_buffer_samples
                            self.data = self.data[excess:,:,:]
                            print(self.data.shape)
                            self._buffer_start_sample += excess
                            print(self._buffer_start_sample)
                        self._offset += n_new * bytes_per_sample

            except Exception as e:
                print("Stream read error:", e)

            time.sleep(poll_interval)

    # ----------------------------------------------------------------
    # Helper to get any slice of data (from buffer or disk)
    # ----------------------------------------------------------------
    def get_data_slice(self, start_sample, stop_sample, wait=True):
        """
        Return data between sample indices [start_sample, stop_sample).
        Waits if file not yet fully written, uses buffer if possible.
        """
        dtype = np.int16
        bytes_per_sample = np.dtype(dtype).itemsize * self.num_channel
        n_samples = stop_sample - start_sample

        # --- Wait until file has enough bytes ---
        if wait:
            expected_bytes = stop_sample * bytes_per_sample
            while True:
                file_size = os.path.getsize(self.file)
                if file_size >= expected_bytes:
                    break
                time.sleep(0.05)

        # --- Try reading from buffer ---
        with self._lock:
            if self.data is not None:
                buf_start = self._buffer_start_sample
                buf_end = buf_start + self.data.shape[0]

                # Fully inside buffer
                if start_sample >= buf_start and stop_sample <= buf_end:
                    rel_start = start_sample - buf_start
                    rel_stop = stop_sample - buf_start
                    return self.data[rel_start:rel_stop, :, :].copy()

        # --- If not in buffer, read from file ---
        offset_bytes = start_sample * bytes_per_sample
        file_size = os.path.getsize(self.file)
        available_bytes = max(0, file_size - offset_bytes)
        to_read_bytes = min(n_samples * bytes_per_sample, available_bytes)

        if to_read_bytes <= 0:
            # Requested slice is not yet written
            return np.zeros((n_samples, self.nbr_row, self.nbr_col), dtype=dtype)

        with open(self.file, "rb") as f:
            f.seek(offset_bytes)
            raw = np.frombuffer(f.read(to_read_bytes), dtype=dtype)

        actual_samples = len(raw) // self.num_channel
        reshaped = raw[:actual_samples*self.num_channel].reshape((actual_samples, self.nbr_row, self.nbr_col))

        # Pad with zeros if slice incomplete
        if actual_samples < n_samples:
            pad_shape = (n_samples - actual_samples, self.nbr_row, self.nbr_col)
            reshaped = np.concatenate([reshaped, np.zeros(pad_shape, dtype=dtype)], axis=0)

        return reshaped


    def get_full_signal(self):
        """
        Return the full signal for a given electrode position (nrow, ncol).
        
        Returns
        -------
        x : np.ndarray
            Time axis in seconds.
        y : np.ndarray
            Signal values (filtered if filters set up).
        """
        with self._lock:
            data = self.data.copy()
            start_sample = self._buffer_start_sample

        # --- Extract one channel
        signal = data.copy().astype(np.float64)

        if self.sos_all is not None:
            try:
                signal = scipy.signal.detrend(signal, type='linear')
                signal = sosfiltfilt(self.sos_all, signal, axis=0)
            except Exception as e:
                print(f"Filter full signal error: {e}")

        if self.denoise: 
            signal = self.apply_denoise(signal)
        # --- Build time axis (seconds)
        n_samples = signal.shape[0]
        x = (np.arange(start_sample, start_sample + n_samples) / self.fs)

        return x, signal
    # ----------------------------------------------------------------
    # Analysis functions
    # ----------------------------------------------------------------
    def setup_filters(self, lowcut, highcut, order, notch_freq, denoise):
        sos = butter(order, [lowcut, highcut], btype='bandpass', fs=self.fs, output='sos')
        sos_notches = []
        for notch in notch_freq:
            for i in range(0, notch[1] + 1):
                if notch[0] * (i + 1) < self.fs / 2:
                    b, a = iirnotch(w0=notch[0] * (i + 1), Q=40, fs=self.fs)
                    sos_notches.append(tf2sos(b, a))
        self.sos_all = np.vstack(sos_notches + [sos])
        self.denoise = denoise

    def compute_psd_with_hanning(signal, nperseg=1024):

        window = windows.hann(nperseg)
        
        freqs, psd = welch(
            signal,
            fs=self.fs,
            window=window,
            nperseg=nperseg,
            axis=-1,       # Compute along the sample axis
            scaling='density',
            average='mean'
        )

        psd_db = 10 * np.log10(psd)
        return freqs, psd_db

    def aply_denoise(self, signal):
        

        return signal 

    def compute_event(self, event_ts):
        """Compute event snapshot, loading from buffer or disk as needed."""
        start = max(0, event_ts - self.snapshot_len)
        stop = event_ts + self.snapshot_len
        signal = self.get_data_slice(start, stop)

        if self.sos_all is not None:
            try:
                signal = scipy.signal.detrend(signal, type='linear')
                signal = sosfiltfilt(self.sos_all, signal, axis=0)
            except Exception as e:
                print("event Filter error:", e)
        if denoise: 
            signal = self.apply_denoise(signal)
        reshaped = signal.reshape(
            (signal.shape[0],
             int(self.nbr_row/self.row_divider), self.row_divider,
             int(self.nbr_col/self.col_divider), self.col_divider)
        )
        reshaped = reshaped.transpose(1, 3, 0, 2, 4).reshape(
            (int(self.num_channel/(self.col_divider*self.row_divider)),
             signal.shape[0], self.row_divider, self.col_divider)
        )
        meaned = np.mean(reshaped, axis=(2, 3))
        self.data_event[event_ts] = meaned

        return meaned

    def reset_xy(self, event_duration=100):

        half_snapshot_sec = event_duration / 1000.0
        self.snapshot_len = int(half_snapshot_sec * self.fs)

        n_samples = 2 * self.snapshot_len
        self.x = np.linspace(-event_duration, event_duration, n_samples, endpoint=True)

        y = np.ones(n_samples)
        y = np.tile(y, (int(self.nbr_col/self.col_divider)*int(self.nbr_row/self.row_divider), 1))
        return self.x, y

    def get_event(self, ts):
        return self.data_event[ts]

    def add_event(self, info):
        print("event " + str(info['sample_number']))
        self.compute_event(info['sample_number'])