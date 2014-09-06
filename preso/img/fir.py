import numpy as np
from matplotlib import pyplot as plt
from scipy import signal

sample_rate = 48e3
cutoff_hz = 8e3
width_hz = 1e3
atten_db = 60

nyq_rate = sample_rate / 2.0                                           
N, beta = signal.kaiserord(atten_db,
        width_hz / nyq_rate)
taps = signal.firwin(N,
        cutoff_hz / nyq_rate,
        window=('kaiser', beta))
n = np.arange(N)
plt.plot(n, taps)
plt.title('Fir Taps')
plt.ylabel('Tap Value')
plt.xlim(0, N)
plt.xlabel('Tap')
plt.savefig('fir.png')
plt.close()

_, h = signal.freqz(taps)
w = np.linspace(0,
        nyq_rate, len(h))
plt.plot(w,
        20 * np.log10(abs(h)),
        'b')
plt.title('Frequency Response')
plt.ylim(-90, 20)
plt.xlim(0, nyq_rate)
plt.ylabel('Amplitude (dB)')
plt.xlabel('Frequncy (Hz)')
plt.savefig('freq-response.png')
