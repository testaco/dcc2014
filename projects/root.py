from myhdl import *

from system import system

def simulation(bus, tops):
    dut = []
    sim = []

    for top in tops:
        print 'Top', top
        dut.append(top.instance(**top.signals_dict()))
        if hasattr(top, 'sim_instance'):
            sim.append(top.sim_instance(**top.sim_signals_dict()))

    if type(bus.masters) == list:
        masters = []
        for m in bus.masters:
            masters.append(iter(m()()))
    else:
        masters = [iter(bus.masters()())]

    print 'Masters', masters

    @instance
    def arbiter():
        while True:
            for master in masters:
                yield master.next()
                while bus.locked:
                    #print 'locked'
                    yield master.next()

    return dut, sim, arbiter

@system.model
class OperatingSystem(object):
    def __init__(self):
        pass

    def interface(self):
        return self

    def _inspect_system(self):
        if not hasattr(self, 'soc'):
            soc = system.node_at_path('/soc')
            self.soc = soc.container
        if not hasattr(self, 'cpu'):
            cpu = system.node_at_path('/soc/cpu')
            self.cpu = cpu.container

    def simulate(self, node_paths, script, name):
        self._inspect_system()

        self.cpu.program(script)

        nodes = []
        for node in node_paths:
            nodes.append(system.node_at_path(node).container)
        t = traceSignals(simulation, self.soc, nodes, name=name)
        s = Simulation(t)
        s.run()

    def alloc(self, name, size):
        self._inspect_system()
        return 0x00010000

    def free(self, name):
        self._inspect_system()
        pass

    def reset(self):
        self._inspect_system()
        yield self.soc.reset()

    def delay(self, cnt):
        self._inspect_system()
        yield self.soc.delay(cnt)

    def transmit(self, addr, data):
        self._inspect_system()
        yield self.soc.transmit(addr, data)

    def receive(self, addr):
        self._inspect_system()
        yield self.soc.receive(addr)
        self.rdata = self.soc.rdata

    @classmethod
    def create_and_connect(cls, parent_path, name, soc):
        path = lambda node, name: '%s#%s' % (node.path, name)
        self = system.add_node(parent_path, name, 'OperatingSystem', {})
        return self

@system.view(r'^(?P<node_path>.*)\.vcd$')
def simulation_view(node_path):
    print node_path
    node = system.node_at_path(node_path)
    print node
    sim = node.container
    print sim
    node_paths, test = sim()
    root = system.node_at_path('/').container
    root.simulate(node_paths, test, sim.name)
