from myhdl import always_seq

def dff(resetn, en, q, d, clk):
    @always_seq(clk.posedge, reset=resetn)
    def logic():
        if en:
            q.next = d
    return logic

from myhdl import Signal, ResetSignal, toVerilog

def convert():
    en, q, d, clk = [Signal(bool(False)) for i in range(4)]
    resetn = ResetSignal(bool(True), bool(False), async=False)
    toVerilog(dff, resetn, en, q, d, clk)

from myhdl import always, delay

def test_dff():
    en, q, d, clk = [Signal(bool(False)) for i in range(4)]
    resetn = ResetSignal(bool(True), bool(False), async=False)
    dff_inst = dff(resetn, en, q, d, clk)

    @always(delay(10))
    def clkgen():
        clk.next = not clk

    @always(clk.negedge)
    def stimulus():
        d.next = 1

    return dff_inst, clkgen, stimulus

from myhdl import traceSignals, Simulation

def simulate(timesteps):
    tb = traceSignals(test_dff)
    sim = Simulation(tb)
    sim.run(timesteps)

if __name__ == '__main__':
    convert()
    simulate(2000)
