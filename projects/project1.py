from myhdl import *

from system import *
s = System('project1')
from soc import *

def project1(
    bus_presetn,
    bus_pclk,
    bus_paddr,
    bus_psel,
    bus_penable,
    bus_pwrite,
    bus_pwdata,
    bus_pready,
    bus_prdata,
    bus_pslverr,
    status_led):
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
                else:
                    state.next = state_t.DONE
            else:
                state.next = state_t.IDLE
        elif state == state_t.DONE:
            bus_pready.next = True
            state.next = state_t.IDLE

    return state_machine

@system.model
class Project1(object):
    def __init__(self, bus, status_led, **kwargs):
        self.bus = bus
        self.status_led = status_led

    def signals_dict(self):
        signals = {}
        signals.update(self.bus())
        signals.update(self.status_led())
        return signals

    @property
    def instance(self):
        return project1

    @classmethod
    def create_and_connect(cls, parent_path, name, pbus, status_led, **kwargs):
        path = lambda node, name: '%s#%s' % (node.path, name)
        self = system.add_node(parent_path, name, 'Project1', kwargs)
        Apb3Bus.connect_slave(pbus, self, prefix='bus_')
        system.add_edge('CallAttrEdge',
            path(status_led, 'signals_dict'),
            path(self, 'status_led'),
            dict(prefix='status_'))
        return self

@system.model
def test_project1():
    bus = system.node_at_path('/soc').container
    status_led = system.node_at_path('/soc/status_led').container
    yield bus.reset() 
    assert not status_led.signal
    yield bus.transmit(0x40, 0x0001)
    assert status_led.signal
    yield bus.receive(0x40)
    assert bus.rdata == 0x0000
    yield bus.transmit(0x40, 0x0000)
    assert not status_led.signal
    yield bus.receive(0x40)
    assert bus.rdata == 0x0000
    raise StopSimulation

# test_project1_hw():  modify project1 such that reading the address 0x40
# returns the value of the status led in the zero'th bit of prdata.
@system.model
def test_project1_hw():
    root = system.node_at_path('/').container
    status_led = system.node_at_path('/soc/status_led').container
    yield root.reset() 
    assert not status_led.signal
    yield root.transmit(0x40, 0x0001)
    assert status_led.signal
    yield root.receive(0x40)
    assert root.rdata == 0x0001
    yield root.transmit(0x40, 0x0000)
    assert not status_led.signal
    yield root.receive(0x40)
    assert root.rdata == 0x0000
    raise StopSimulation

@system.register_load
def load():
    resetn = Reset.create_and_connect('/', 'resetn', async=False)
    clk = Clock.create_and_connect('/', 'clk', int(1e9/10e6))
    soc = BusMatrix.create('/', 'soc', resetn, clk, duration=int(1e9/10e6),
            address_mask=0xff)
    pbus = Apb3Bus.create('/soc', 'pbus', soc, duration=int(1e9/10e6), verbose=True)
    status_led = Led.create_and_connect('/soc', 'status_led')
    project1 = Project1.create_and_connect('/soc', 'project1', pbus, status_led)
    cpu = Cpu.create_and_connect('/soc', 'cpu', soc)
    sim = Sim.create_and_connect('/soc', 'test_project1', 'test_project1',
            '/soc/project1')

@system.register_execute
def execute():
    system.dispatch('/resource-tree.latex')

    print
    print "----------------"
    print 'Generating the verilog'
    print

    system.dispatch('/soc/project1.v')

    print
    print "----------------"
    print 'Running the simulation'
    print

    system.dispatch('/soc/test_project1.vcd')


if __name__ == '__main__':
    run()
