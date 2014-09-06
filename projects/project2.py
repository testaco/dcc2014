import numpy as np
from myhdl import *

from system import *
s = System('project2')
from soc import *

def slave(
    bus_presetn, bus_pclk, bus_paddr, bus_psel, bus_penable, bus_pwrite,
    bus_pwdata, bus_pready, bus_prdata, bus_pslverr,
    fifo_wclk, fifo_we, fifo_data, fifo_full, fifo_afull,
    fifo_wack, fifo_overflow, fifo_wrcnt, status_led):

    state_t = enum('IDLE', 'DONE',)
    state = Signal(state_t.IDLE)

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

    return state_machine

@system.model
class Slave(object):
    def __init__(self, pbus, fifo, status_led):
        self.bus = pbus
        self.fifo = fifo
        self.status_led = status_led
    
    def signals_dict(self):
        signals = self.bus()
        signals.update(self.fifo())
        signals.update(self.status_led())
        return signals

    @property
    def instance(self):
        return slave

    @classmethod
    def create_and_connect(cls, parent_path, name, pbus, fifo, status_led):
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
        return self

def project2(
        bus_presetn, bus_pclk, bus_paddr, bus_psel, bus_penable,
        bus_pwrite, bus_pwdata, bus_pready, bus_prdata, bus_pslverr,
        status_led, conv_clk, instances):
    i = []
    for f, d in instances:
        i.append(f(**d))
    return i

@system.model
class Project2(object, ToplevelMixin):
    root = '/soc/pbus/project2'

    def __init__(self, bus, status_led, conv_clk, **kwargs):
        self.bus = bus
        self.status_led = status_led
        self.conv_clk = conv_clk

    def signals_dict(self):
        signals = { 'instances': self.instances() }
        signals.update(self.bus())
        signals.update(self.status_led())
        signals.update(self.conv_clk())
        return signals

    @property
    def instance(self):
        return project2

    @classmethod
    def create_and_connect(cls, parent_path, name, resetn, clk, pbus, status_led, **kwargs):
        path = lambda node, name: '%s#%s' % (node.path, name)
        self = system.add_node(parent_path, name, 'Project2', kwargs)
        self_path = self.path

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

        fifo = Fifo.create_and_connect(self_path, 'fifo',
                resetn, clk, conv_clk, width=32, depth=128)

        slave = Slave.create_and_connect(self_path, 'slave',
                pbus, fifo, status_led)

        clearn = Synchronize.create_and_connect(self_path, 'clearn',
                conv_clk, resetn, bool(True))
        dspen = Synchronize.create_and_connect(self_path, 'dspen',
                conv_clk, status_led, bool(False))
        dsp = DspFlow.create(self_path, 'dsp', clearn, conv_clk)
        dsp_signal = DspFlow.create_net(dsp, 'signal', width=32)

        fifo_source = FifoSource.create_and_connect(dsp.path, 'fifo_source',
                dspen, fifo, dsp, 'signal')

        scope_sink = ScopeSink.create_and_connect(dsp.path, 'scope',
                clearn, conv_clk, dsp, 'signal')

        return self

@system.register_load
def load():
    resetn = Reset.create_and_connect('/', 'resetn', async=False)
    clk = Clock.create_and_connect('/', 'clk', int(10e6))
    status_led = Led.create_and_connect('/', 'status_led')
    soc = BusMatrix.create('/', 'soc', resetn, clk, duration=int(10e6),
        address_mask=0xffff)
    cpu = Cpu.create_and_connect('/soc', 'cpu', soc)
    pbus = Apb3Bus.create('/soc', 'pbus', soc, duration=int(10e6), verbose=False)
    project2 = Project2.create_and_connect('/soc/pbus', 'project2',
        resetn, clk, pbus, status_led)
    sim = Sim.create_and_connect('/', 'test_project2', 'test_project2',
            '/soc/pbus/project2')

@system.model
def test_project2():
    root = system.node_at_path('/').container
    status_led = system.node_at_path('/status_led').container
    conv_clk = system.node_at_path('/soc/pbus/project2/conv_clk').container
    scope = system.node_at_path('/soc/pbus/project2/dsp/scope').container

    yield root.reset() 
    assert not status_led.signal

    sample_rate = conv_clk.freq
    n = np.arange(64)
    freq = 24e3
    print 'sample_rate', sample_rate, 'freq', freq
    samples = np.sin(2 * np.pi * n * (freq / sample_rate))

    for sample in samples:
        s = intbv(int(sample * (2**31 - 1)))[32:]
        yield root.transmit(0x50, s)

    yield root.transmit(0x40, 0x0001)
    assert status_led.signal

    while len(scope.samples) < 64:
        yield root.delay(1)

    scope.plot()
    scope.savefig('test_project2.png')

    raise StopSimulation

@system.register_execute
def execute():
    print
    print "----------------"
    print 'Generating the verilog'
    print

    system.dispatch('/soc/pbus/project2.v')

    print
    print "----------------"
    print 'Running the simulation'
    print

    system.dispatch('/test_project2.vcd')

    system.dispatch('/resource-tree.latex')


if __name__ == '__main__':
    run()
