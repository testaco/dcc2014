from myhdl import *

from system import *
from root import *
from bus import *
from mem import *
from cpu import *
from dsp import *
from viz import *
from hci import *

@system.model
class CallAttrEdge(object):
    def __init__(self, system, fr, to, kwargs):
        from_path, from_attr = fr.split('#')
        to_path, to_attr = to.split('#')
        from_node = system.node_at_path(from_path)
        to_node = system.node_at_path(to_path)
        self.system = system
        self.from_node = from_node
        self.from_attr = from_attr
        self.to_node = to_node
        self.to_attr = to_attr
        self.kwargs = kwargs

        # This block starts by lazily creating edges as scalar values;
        # then if a second cone is added, it turns the edge into a list;
        # Subsequent edges are added to the list.
        if from_attr in from_node.outputs:
            if type(from_node.outputs[from_attr]) == list:
                from_node.outputs[from_attr].append(self)
            else:
                from_node.outputs[from_attr] = [
                    from_node.outputs[from_attr],
                    self
                ]
        else:
            from_node.outputs[from_attr] = self

        # Same for inputs.
        if to_attr in to_node.inputs:
            if type(to_node.inputs[to_attr]) == list:
                to_node.inputs[to_attr].append(self)
            else:
                to_node.inputs[to_attr] = [
                    to_node.inputs[to_attr],
                    self
                ]
        else:
            to_node.inputs[to_attr] = self

    def __call__(self, **kwargs):
        kw = dict(self.kwargs)
        kw.update(kwargs)
        return getattr(self.from_node.container, self.from_attr)(**kw)

    def __getstate__(self):
        state = {
            '__class__': type(self).__name__,
            'from': '%s#%s' % (self.from_node.path, self.from_attr),
            'to': '%s#%s' % (self.to_node.path, self.to_attr),
        }
        state.update(self.kwargs)
        return state

def clock(clk, duration):
    @instance
    def _driver():
        while True:
            clk.next = True
            yield delay(duration // 2)
            clk.next = False
            yield delay(duration // 2)
    return _driver

@system.model
class Clock(object):
    def __init__(self, freq):
        self.signal = Signal(bool(False))
        self.freq = freq
        self.duration = int(1e9 / freq)

    def signals_dict(self, name=None):
        if name is None:
            name = 'clk'
        signals = { name: self.signal }
        signals['duration'] = self.duration
        return signals

    def out(self, name=None):
        return { name: self.signal }

    @property
    def sim_instance(self):
        return clock

    @classmethod
    def create_and_connect(cls, parent_path, name, freq):
        return system.add_node(parent_path, name, 'Clock', {'freq': freq})

@system.model
class Flag(object):
    def __init__(self, default):
        self.signal = Signal(bool(default))

    def signals_dict(self, name=None):
        signals = { name: self.signal }
        return signals

    @classmethod
    def create_and_connect(cls, parent_path, name, default=False):
        return system.add_node(parent_path, name, 'Flag', {'default': default })

def synchronize(clk, other_signal, signal_delay, signal):
    @always(clk.posedge)
    def synchronizer():
        signal_delay.next = other_signal
        signal.next = signal_delay

    return synchronizer

@system.model
class Synchronize(object):
    """A two flip-flop synchronizer between clock domains."""
    def __init__(self, clk, other_signal, default):
        self.clk = clk
        self.other_signal = other_signal
        self.signal_delay = Signal(default)
        self.signal = Signal(default)

    def signals_dict(self):
        signals = dict(
            signal_delay=self.signal_delay,
            signal=self.signal,
        )
        signals.update(self.clk())
        signals.update(self.other_signal())
        return signals

    def out(self, name):
        return { name: self.signal }

    @property
    def instance(self):
        return synchronize

    @classmethod
    def create_and_connect(cls, parent_path, name, clk, sig, default):
        path = lambda node, name: '%s#%s' % (node.path, name)
        self = system.add_node(parent_path, name, 'Synchronize', {'default': default})
        system.add_edge('CallAttrEdge',
            path(clk, 'out'),
            path(self, 'clk'),
            dict(name='clk'))
        system.add_edge('CallAttrEdge',
            path(sig, 'signals_dict'),
            path(self, 'other_signal'),
            dict(name='other_signal'))
        return self

@system.model
class Mem(object):
    def __init__(self, width, depth):
        self.width = width
        self.lg2width = int(ceil(log(width / 8, 2)))
        self.depth = depth
        self.mem = [0 for i in xrange(depth)]

    def interface(self):
        return self

    def reset(self):
        for i in xrange(self.depth):
            self.mem[i] = 0

    def delay(self, n):
        pass

    def transmit(self, addr, data):
        self.mem[(addr & 0xffff) >> self.lg2width] = data
        #print 'write', hex(addr), hex(self.mem[(addr & 0xffff) >> self.lg2width])

    def receive(self, addr):
        self.rdata = self.mem[(addr & 0xffff) >> self.lg2width]
        #print 'read', hex(addr), hex(self.rdata)

    @classmethod
    def create_and_connect(cls, parent_path, name, bus, width, depth):
        path = lambda node, name: '%s#%s' % (node.path, name)
        self = system.add_node(parent_path, name, 'Mem', { 'width': width, 'depth': depth })
        system.add_edge('CallAttrEdge',
            path(self, 'interface'),
            path(bus, 'slaves'))

class DmaChannel(object):
    def __init__(self, ready):
        self.ready = ready
        self.reset()

    def reset(self):
        self.src_addr = 0
        self.src_incr = 0
        self.dest_addr = 0
        self.dest_incr = 0
        self.count = 0

@system.model
class Dma(object):
    def __init__(self, bus, ready):
        self.bus = bus()
        self.channel = DmaChannel(ready()['ready'])

    def execute(self):
        def dma_master():
            while True:
                channel = self.channel
                if channel.ready and channel.count > 0:
                    #print 'locking'
                    self.bus.locked = True
                    #print 'locked?', self.bus.locked
                    yield self.bus.receive(channel.src_addr)
                    val = self.bus.rdata
                    self.bus.locked = False
                    #print 'VAL', val
                    # TODO: okay so the mess is that another master runs between the last yield statement and this; so I should create a Transaction object for each receive or lock the bus; and that's why using cpu.load() will be better; if I can figure it out!
                    yield self.bus.transmit(channel.dest_addr, val)
                    #print 'dma ready', channel.ready, 'src', hex(channel.src_addr), 'dest', hex(channel.dest_addr), 'val', hex(val), channel.src_incr
                    channel.src_addr += channel.src_incr
                    channel.dest_addr += channel.dest_incr
                    channel.count -= 1
                else:
                    yield self.bus.delay(1)
        return dma_master

    def interface(self):
        return self

    def reset(self):
        channel = self.channel
        channel.reset()

    def delay(self, n):
        pass

    def transmit(self, addr, data):
        channel = self.channel
        if addr & 0x1f == 0x00:
            channel.src_addr = data
        elif addr & 0x1f == 0x04:
            channel.src_incr = data
        elif addr & 0x1f == 0x08:
            channel.dest_addr = data
        elif addr & 0x1f == 0x0c:
            channel.dest_incr = data
        elif addr & 0x1f == 0x10:
            channel.count = data

    def receive(self, addr):
        channel = self.channel
        if addr & 0x1f == 0x00:
            self.rdata = channel.src_addr
        elif addr & 0x1f == 0x04:
            self.rdata = channel.src_incr
        elif addr & 0x1f == 0x08:
            self.rdata = channel.dest_addr
        elif addr & 0x1f == 0x0c:
            self.rdata = channel.dest_incr
        elif addr & 0x1f == 0x10:
            self.rdata = channel.count

    @classmethod
    def create_and_connect(cls, parent_path, name, bus, ready):
        self = system.add_node(parent_path, name, 'Dma')
        path = lambda node, name: '%s#%s' % (node.path, name)
        system.add_edge('CallAttrEdge',
            path(self, 'execute'),
            path(bus, 'masters'))
        system.add_edge('CallAttrEdge',
            path(self, 'interface'),
            path(bus, 'slaves'))
        system.add_edge('CallAttrEdge',
            path(bus, 'interface'),
            path(self, 'bus'))
        system.add_edge('CallAttrEdge',
            path(ready, 'signals_dict'),
            path(self, 'ready'),
            dict(name='ready'))

@system.model
class Sim(object):
    def __init__(self, node_paths, func):
        self.node_paths = node_paths
        self.name = func
        self.func = system.models[func]

    def __call__(self):
        return self.node_paths, self.func

    @classmethod
    def create_and_connect(cls, parent_path, name, func, *node_paths):
        self = system.add_node(parent_path, name, 'Sim', {
                'func': func,
                'node_paths': node_paths})
        return self

def toplevel_sim(instances):
    i = []
    for f, d in instances:
        i.append(f(**d))
    return i

class ToplevelMixin():
    def instances(self):
        instances = []
        def make_instances(n):
            print n.path, hasattr(n.container, 'instance')
            if hasattr(n.container, 'instance'):
                c = n.container
                instances.append((c.instance, c.signals_dict()))
        system.traverse(self.root, make_instances, include_root=False)
        return instances

    def sim_instances(self):
        instances = []
        def make_instances(n):
            print n.path, hasattr(n.container, 'sim_instance')
            if hasattr(n.container, 'sim_instance'):
                c = n.container
                instances.append((c.sim_instance, c.signals_dict()))
        system.traverse(self.root, make_instances, include_root=False)
        return instances

    def sim_signals_dict(self):
        return { 'instances': self.sim_instances() }

    @property
    def sim_instance(self):
        return toplevel_sim

@system.view(r'^(?P<node_path>.*)\.v$')
def hdl_view(node_path):
    print node_path
    node = system.node_at_path(node_path)
    print node
    hdl = node.container
    print hdl, hdl.signals_dict()
    from myhdl import toVerilog
    return toVerilog(hdl.instance, **hdl.signals_dict())
