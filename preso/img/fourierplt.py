import numpy as np
from matplotlib import pyplot as plt
sample_rate = 48e3
freq = 7e3
N = 2048
n = np.arange(N)
y = np.sin(2 * np.pi * freq \
        * (n / sample_rate)) \
        + np.random.normal(
                0, .1, N)
frq = np.fft.fftfreq(len(n),
        1./sample_rate)
Y = np.fft.fft(y)
power_Y = np.abs(Y) ** 2
power_db = -10 * np.log10(
        power_Y / np.max(power_Y))
plt.plot(frq[0:len(frq)/2],
        power_db[0:len(frq)/2],
        'b')
plt.title('Signal over Frequency')
plt.ylim(60, 0)
plt.ylabel('Attenuation (dB)')
plt.xlim(0, sample_rate / 2)
plt.xlabel('Frequency (Hz)')
plt.savefig("fourierplt.png")
