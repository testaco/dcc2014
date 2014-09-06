import numpy as np
from matplotlib import pyplot as plt
from scipy import signal

from myhdl import *

from system import system

@system.model
class DspNet(object):
    def __init__(self, os, width, depth):
        self.valid = Signal(bool(False))
        self.data = Signal(intbv(0)[width:])

    def signals_dict(self, prefix=None):
        if prefix is None:
            prefix = ''
        return {
            '%svalid' % prefix: self.valid,
            '%sdata' % prefix: self.data,
        }

    @classmethod
    def create(cls, parent_path, name, width, depth=1):
        self = system.add_node(parent_path, name, 'DspNet', {
            'width': width,
            'depth': depth,
        })
        return self

    @classmethod
    def connect(cls, self, node, to, prefix=None):
        path = lambda node, name: '%s#%s' % (node.path, name)
        system.add_edge('CallAttrEdge',
            path(self, 'signals_dict'),
            path(node, to),
            dict(prefix=prefix))

@system.model
class DspFlow(object):
    def __init__(self, nodes, os, clearn=None, clk=None, net_class=None):
        self.nodes = nodes
        self.clearn = clearn
        self.clk = clk
        self.os = os

    def interface(self):
        return self

    @classmethod
    def create(cls, parent_path, name, clearn, clk, net_class='DspNet'):
        path = lambda node, name: '%s#%s' % (node.path, name)
        self = system.add_node(parent_path, name, 'DspFlow', {
            'net_class': net_class,
        })
        os = system.node_at_path('/')
        system.add_edge('CallAttrEdge',
            path(os, 'interface'),
            path(self, 'os'))
        if clearn:
            system.add_edge('CallAttrEdge',
                path(clearn, 'signals_dict'),
                path(self, 'clearn'))
        if clk:
            system.add_edge('CallAttrEdge',
                path(clk, 'out'),
                path(self, 'clk'))
        return self

    @classmethod
    def create_net(cls, self, net, width, depth=1, **kwargs):
        net_class = system.models[self.kwargs['net_class']]
        net_node = net_class.create(self.path, net, width, depth, **kwargs)
        os = system.node_at_path('/')
        path = lambda node, name: '%s#%s' % (node.path, name)
        system.add_edge('CallAttrEdge',
            path(os, 'interface'),
            path(net_node, 'os'))
        return net_node

    @classmethod
    def connect(cls, self, net, node, to, width=32, depth=1, prefix=None):  # TODO
        net_class = system.models[self.kwargs['net_class']]
        if net in self.children:
            net_node = self.children[net]
        else:
            net_node = DspFlow.create_net(self, net, width)
        net_class.connect(net_node, node, to, prefix)
        path = lambda node, name: '%s#%s' % (node.path, name)
        system.add_edge('CallAttrEdge',
            path(node, 'interface'),
            path(self, 'nodes'))

def fifo_source(
        en,
        fifo_rclk,
        fifo_re,
        fifo_Q,
        fifo_empty,
        fifo_aempty,
        fifo_dvld,
        fifo_underflow,
        fifo_rdcnt,
        out_valid,
        out_data):

    @always_comb
    def assignments():
        fifo_re.next = en
        out_valid.next = fifo_dvld
        out_data.next = fifo_Q

    return assignments

@system.model
class FifoSource(object):
    def __init__(self, en, fifo, out):
        self.en = en
        self.fifo = fifo
        self.out = out

    @property
    def instance(self):
        return fifo_source

    def signals_dict(self):
        signals = dict(self.en())
        signals.update(self.fifo())
        signals.update(self.out())
        return signals

    @classmethod
    def create_and_connect(cls, parent_path, name, en, fifo, dspflow, net):
        path = lambda node, name: '%s#%s' % (node.path, name)
        self = system.add_node(parent_path, name, 'FifoSource')
        system.add_edge('CallAttrEdge',
            path(en, 'out'),
            path(self, 'en'),
            dict(name='en'))
        system.add_edge('CallAttrEdge',
            path(fifo, 'read_port'),
            path(self, 'fifo'),
            dict(prefix='fifo_'))
        DspFlow.connect(dspflow, net, self, 'out', prefix='out_')
        return self

def scope_sink(clearn, clk, in_valid, in_data, samples):
    @always(clk.posedge)
    def sampler():
        if not clearn:
            del samples[:]
        if in_valid:
            samples.append(int(in_data.signed()))

    return sampler

@system.model
class ScopeSink(object):
    def __init__(self, clearn, clk, signal):
        self.clearn = clearn
        self.clk = clk
        self.signal = signal
        self.samples = []

    @property
    def sim_instance(self):
        return scope_sink

    def signals_dict(self):
        signals = { 'samples': self.samples }
        print self.clearn(), self.clk(), self.signal()
        signals.update(self.clearn())
        signals.update(self.clk())
        signals.update(self.signal())
        return signals

    def plot(self):
        n = np.arange(len(self.samples))
        print self.samples
        y = np.array([s for s in self.samples])
        plt.plot(n, y)
        plt.xlim(0, len(self.samples) - 1)

    def show(self):
        plt.show()

    def savefig(self, fname, **kwargs):
        plt.savefig(fname, **kwargs)

    @classmethod
    def create_and_connect(cls, parent_path, name, clearn, clk, dspflow, net):
        path = lambda node, name: '%s#%s' % (node.path, name)
        self = system.add_node(parent_path, name, 'ScopeSink', {})
        system.add_edge('CallAttrEdge',
            path(clearn, 'out'),
            path(self, 'clearn'),
            dict(name='clearn'))
        system.add_edge('CallAttrEdge',
            path(clk, 'out'),
            path(self, 'clk'),
            dict(name='clk'))
        DspFlow.connect(dspflow, net, self, 'signal', prefix='in_')
        return self

@system.model
class Fir(object):
    @classmethod
    def design_low_pass(cls, sample_rate, cutoff_hz, width_hz, ripple_db):
        nyq_rate = sample_rate / 2.0
        N, beta = signal.kaiserord(ripple_db, width_hz / nyq_rate)
        taps = signal.firwin(N, cutoff_hz / nyq_rate, window=('kaiser', beta))
        unweighted_taps = list(taps)
        return taps
