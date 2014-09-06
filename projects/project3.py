import numpy as np
from myhdl import *

from system import *
s = System('project3')
from soc import *

def slave(
    bus_presetn, bus_pclk, bus_paddr, bus_psel, bus_penable, bus_pwrite,
    bus_pwdata, bus_pready, bus_prdata, bus_pslverr,
    fifo_wclk, fifo_we, fifo_data, fifo_full, fifo_afull,
    fifo_wack, fifo_overflow, fifo_wrcnt, status_led, dmaready):

    state_t = enum('IDLE', 'DONE',)
    state = Signal(state_t.IDLE)

    @always_comb
    def assignments():
        dmaready.next = not fifo_full

    @always_seq(bus_pclk.posedge, reset=bus_presetn)
    def state_machine():
        bus_pslverr.next = 0
        if state == state_t.IDLE:
            bus_pready.next = True
            if bus_penable and bus_psel:
                if bus_paddr[8:] == 0x40:
                    if bus_pwrite:
                        status_led.next = bus_pwdata[0]
                        state.next = state_t.DONE
                    else:
                        bus_prdata.next = 0
                        state.next = state_t.DONE
                elif bus_paddr[8:] == 0x50:
                    fifo_we.next = bus_pwrite
                    #print 'sample-in ', bus_pwdata.signed()
                    fifo_data.next = bus_pwdata
                    state.next = state_t.DONE
                else:
                    state.next = state_t.DONE
            else:
                state.next = state_t.IDLE
        elif state == state_t.DONE:
            bus_pready.next = True
            fifo_we.next = False
            state.next = state_t.IDLE

    return state_machine, assignments

@system.model
class Slave(object):
    def __init__(self, pbus, fifo, status_led, dmaready):
        self.bus = pbus
        self.fifo = fifo
        self.status_led = status_led
        self.dmaready = dmaready
    
    def signals_dict(self):
        signals = self.bus()
        signals.update(self.fifo())
        signals.update(self.status_led())
        signals.update(self.dmaready())
        return signals

    @property
    def instance(self):
        return slave

    @classmethod
    def create_and_connect(cls, parent_path, name, pbus, fifo, status_led, dmaready):
        path = lambda node, name: '%s#%s' % (node.path, name)
        self = system.add_node(parent_path, name, 'Slave', {})
        system.add_edge('CallAttrEdge',
            path(pbus, 'signals_dict'),
            path(self, 'pbus'),
            dict(prefix='bus_'))
        system.add_edge('CallAttrEdge',
            path(fifo, 'write_port'),
            path(self, 'fifo'),
            dict(prefix='fifo_'))
        system.add_edge('CallAttrEdge',
            path(status_led, 'signals_dict'),
            path(self, 'status_led'),
            dict(prefix='status_'))
        system.add_edge('CallAttrEdge',
            path(dmaready, 'signals_dict'),
            path(self, 'dmaready'),
            dict(name='dmaready'))
        return self

def project3(
        bus_presetn, bus_pclk, bus_paddr, bus_psel, bus_penable,
        bus_pwrite, bus_pwdata, bus_pready, bus_prdata, bus_pslverr,
        status_led, conv_clk, dmaready, instances):
    i = []
    for f, d in instances:
        i.append(f(**d))
    return i

@system.model
class Project3(object, ToplevelMixin):
    root = '/soc/pbus/project3'

    def __init__(self, bus, status_led, conv_clk, dmaready, **kwargs):
        self.bus = bus
        self.status_led = status_led
        self.conv_clk = conv_clk
        self.dmaready = dmaready

    def signals_dict(self):
        signals = { 'instances': self.instances() }
        signals.update(self.bus())
        signals.update(self.status_led())
        signals.update(self.conv_clk())
        signals.update(self.dmaready())
        return signals

    @property
    def instance(self):
        return project3

    @classmethod
    def create_and_connect(cls, parent_path, name, resetn, clk, pbus, status_led, dmaready, **kwargs):
        path = lambda node, name: '%s#%s' % (node.path, name)
        self = system.add_node(parent_path, name, 'Project3', kwargs)
        self_path = self.path

        system.add_edge('CallAttrEdge',
            path(dmaready, 'signals_dict'),
            path(self, 'dmaready'),
            dict(name='dmaready'))

        Apb3Bus.connect_slave(pbus, self, prefix='bus_')
        system.add_edge('CallAttrEdge',
            path(status_led, 'signals_dict'),
            path(self, 'status_led'),
            dict(prefix='status_'))

        conv_clk = Clock.create_and_connect(self_path, 'conv_clk', int(1e6))
        system.add_edge('CallAttrEdge',
            path(conv_clk, 'out'),
            path(self, 'conv_clk'),
            dict(name='conv_clk'))

        clearn = Synchronize.create_and_connect(self_path, 'clearn',
                conv_clk, resetn, bool(True))
        dsp = DspFlow.create(self_path, 'dsp', clearn, conv_clk)

        dspen = Synchronize.create_and_connect(self_path, 'dspen',
                conv_clk, status_led, bool(False))
        fifo = Fifo.create_and_connect(self_path, 'fifo',
                resetn, clk, conv_clk, width=32, depth=128)
        fifo_source = FifoSource.create_and_connect(dsp.path, 'fifo_source',
                dspen, fifo, dsp, 'signal')

        #fir = Fir.create_and_connect(dsp.path, 'fir',
        #    len(Fir.design_low_pass(48e3, 8e3, 1e3, 40)))

        scope_sink = ScopeSink.create_and_connect(dsp.path, 'scope',
                clearn, conv_clk, dsp, 'signal')

        slave = Slave.create_and_connect(self_path, 'slave',
                pbus, fifo, status_led, dmaready)

        return self

@system.register_load
def load():
    resetn = Reset.create_and_connect('/', 'resetn', async=False)
    clk = Clock.create_and_connect('/', 'clk', int(10e6))
    status_led = Led.create_and_connect('/', 'status_led')
    soc = BusMatrix.create('/', 'soc', resetn, clk, duration=int(10e6),
        address_mask=0xffff)
    pbus = Apb3Bus.create('/soc', 'pbus', soc, duration=int(10e6), verbose=False)
    dmaready = Flag.create_and_connect('/soc', 'dmaready')
    project3 = Project3.create_and_connect('/soc/pbus', 'project3',
        resetn, clk, pbus, status_led, dmaready)

    emc = Mem.create_and_connect('/soc', 'mem', soc, width=32, depth=512)
    dma = Dma.create_and_connect('/soc', 'dma', soc, dmaready)
    cpu = Cpu.create_and_connect('/soc', 'cpu', soc)

    dsp = DspFlowController.create_and_connect('/soc/cpu',
            'daemon')
    dsp_signal = DspFlow.create_net(dsp, 'signal',
            width=32, depth=512)
    signal_source = SignalSource.create_and_connect('/soc/cpu/daemon/dsp',
            'signal_source', dsp, 'signal')
    audio_freq = Slider.create('/', 'audio_freq',
            300, 12e3, 10, 1e3)
    audio_sample_rate = Slider.create('/', 'audio_sample_rate',
            8e3, 96e3, 8e3, 48e3)
    Slider.connect(audio_freq, signal_source, 'freq')
    Slider.connect(audio_sample_rate, signal_source, 'sample_rate')
    dma_sink = DmaSink.create_and_connect('/soc/cpu/daemon/dsp',
            'dma_sink', dsp, 'signal')

    sim = Sim.create_and_connect('/', 'test_project3', 'test_project3',
            '/soc/pbus/project3')

@system.model
def test_project3():
    root = system.node_at_path('/').container
    daemon = system.node_at_path('/soc/cpu/daemon').container
    conv_clk = system.node_at_path('/soc/pbus/project3/conv_clk').container
    scope = system.node_at_path('/soc/pbus/project3/dsp/scope').container
    yield root.reset()

    N = 128
    sample_rate = conv_clk.freq

    yield daemon.start()

    yield root.transmit(0x40, 0x0001)

    while len(scope.samples) < N - 1:
        yield daemon.step()

    scope.plot()
    scope.savefig('test_project3.png')

    raise StopSimulation

@system.register_execute
def execute():
    system.dispatch('/resource-tree.latex')

    print
    print "----------------"
    print 'Generating the verilog'
    print

    system.dispatch('/soc/pbus/project3.v')

    print
    print "----------------"
    print 'Running the simulation'
    print

    system.dispatch('/test_project3.vcd')

if __name__ == '__main__':
    run()
