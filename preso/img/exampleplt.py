import numpy as np
from matplotlib import pyplot as plt
sample_rate = 48e3
freq = 7e3
N = 256
n = np.arange(N)
y = np.sin(2 * np.pi * freq \
        * (n / sample_rate)) \
        + np.random.normal(
                0, .1, N)
plt.plot(n, y)
plt.title('Signal over Time')
plt.ylabel('Amplitude')
plt.xlim(0, N)
plt.xlabel('Time (samples)')
plt.savefig("exampleplt.png")
