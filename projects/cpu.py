import numpy as np
from myhdl import intbv, modbv

from system import system

from dsp import DspFlow

@system.model
class Cpu(object):
    def program(self, func):
        self.func = func

    def execute(self):
        def _exec():
            for i in self.func():
                yield i
        return _exec

    # TODO: write this!
    def load(self):
        pass

    @classmethod
    def create_and_connect(cls, parent_path, name, bus):
        self = system.add_node(parent_path, name, 'Cpu')
        path = lambda node, name: '%s#%s' % (node.path, name)
        system.add_edge('CallAttrEdge',
            path(self, 'execute'),
            path(bus, 'masters'))
        return self

@system.model
class MemFifoDspNet(object):
    def __init__(self, name, width, depth, os):
        self.name = name
        self.width = width
        self.depth = depth
        self.os = os

    def interface(self):
        return self

    def mem(self):
        if not hasattr(self, '_mem'):
            self._mem = self.os().alloc(self.name, (self.width >> 2) * self.depth)
            self._wrptr = 0
            self._rdptr = 0
        return self._mem

    @property
    def wrptr(self):
        self.mem()
        return self._mem + self._wrptr

    @property
    def wrcnt(self):
        return (self.depth - self.rdcnt)

    def write(self, cnt):
        self._wrptr = modbv(self._wrptr + cnt, min=0, max=self.depth)
        #print 'net-wrote', cnt, 'wrcnt', self.wrcnt, 'rdcnt', self.rdcnt

    @property
    def rdptr(self):
        self.mem()
        return self._mem + self._rdptr

    @property
    def rdcnt(self):
        return abs(self.wrptr - self.rdptr) >> 2
    
    def read(self, cnt):
        self._rdptr = modbv(self._rdptr + cnt, min=0, max=self.depth)
        #print 'net-readd cnt', cnt, 'wrcnt', self.wrcnt, 'rdcnt', self.rdcnt

    @classmethod
    def create(cls, parent_path, name, width, depth):
        path = lambda node, name: '%s#%s' % (node.path, name)
        self = system.add_node(parent_path, name, 'MemFifoDspNet', {
            'name': name,
            'width': width,
            'depth': depth,
        })
        return self

    @classmethod
    def connect(cls, self, node, to, prefix=None):
        path = lambda node, name: '%s#%s' % (node.path, name)
        system.add_edge('CallAttrEdge',
            path(self, 'interface'),
            path(node, to))


@system.model
class DspFlowController(object):
    def __init__(self, os, dsp):
        self.os = os
        self.dsp = dsp

    def start(self):
        self.os = self.os()
        self.dsp = self.dsp()

        if type(self.dsp.nodes) != list:
            self.nodes = [self.dsp.nodes()]
        else:
            self.nodes = [n() for n in self.dsp.nodes]

        for node in self.nodes:
            yield node.start(self.os)

    def step(self):
        for node in self.nodes:
            yield node.work(self.os)

    @classmethod
    def create_and_connect(cls, parent_path, name):
        path = lambda node, name: '%s#%s' % (node.path, name)
        os = system.node_at_path('/')
        self = system.add_node(parent_path, name, 'DspFlowController', {})
        system.add_edge('CallAttrEdge',
            path(os, 'interface'),
            path(self, 'os'))
        dsp = system.add_node(self.path, 'dsp', 'DspFlow', {
            'net_class': 'MemFifoDspNet' })
        system.add_edge('CallAttrEdge',
            path(dsp, 'interface'),
            path(self, 'dsp'))
        system.add_edge('CallAttrEdge',
            path(os, 'interface'),
            path(dsp, 'os'))
        return dsp

@system.model
class SignalSource(object):
    def __init__(self, out, freq, sample_rate):
        self.out = out
        self.freq = freq
        self.sample_rate = sample_rate
        self.n = 0

    def interface(self):
        return self

    def start(self, os):
        print os
        #print 'SIGNAL', self.out(), 'freq', self.freq(), 'samp_rate', self.sample_rate()

    def work(self, os):
        out = self.out()
        if out.wrcnt > 0 and out.rdcnt < 16:
            N = min(out.wrcnt, 64)
            n = np.arange(self.n, self.n + N)
            samples = np.sin(2 * np.pi * n * (float(self.freq()) / self.sample_rate()))
            for sample in samples:
                s = intbv(int(sample * (2**31 - 1)))[32:]
                #print 'sample-out', s.signed()
                yield os.transmit(out.wrptr, s)
                out.write(4)
            self.n += N
            #print 'wrote', N, 'samples'
            #from myhdl import StopSimulation
            #raise StopSimulation

    @classmethod
    def create_and_connect(cls, parent_path, name, dspflow, net):
        path = lambda node, name: '%s#%s' % (node.path, name)
        self = system.add_node(parent_path, name, 'SignalSource', {})
        DspFlow.connect(dspflow, net, self, 'out', prefix='out_')
        return self

@system.model
class DmaSink(object):
    def __init__(self, in_, base, out_addr):
        self.in_ = in_
        self.base = base
        self.out_addr = out_addr
        self.last_cnt = 0

    def interface(self):
        return self

    def start(self, os):
        print os
        #print 'SIGNAL IN', self.in_()

    def work(self, os):
        in_ = self.in_()
        if in_.rdcnt:
            yield os.receive(self.base + 0x10) # CNT
            if os.rdata == 0:
                yield in_.read(self.last_cnt << 2)
                if self.last_cnt > 0:
                    #raise StopSimulation
                    pass

                yield os.transmit(self.base + 0x00, in_.rdptr) # SRC ADDR
                yield os.transmit(self.base + 0x04, in_.width >> 3) # SRC INCR
                yield os.transmit(self.base + 0x08, self.out_addr) # DEST ADDR
                yield os.transmit(self.base + 0x0c, 0) # DEST INCR
                cnt = min(in_.rdcnt, 64)
                self.last_cnt = cnt
                #print 'dma transfer', cnt
                yield os.transmit(self.base + 0x10, cnt)

    @classmethod
    def create_and_connect(cls, parent_path, name, dspflow, net):
        path = lambda node, name: '%s#%s' % (node.path, name)
        self = system.add_node(parent_path, name, 'DmaSink', {
            'base': 0x00020000,
            'out_addr': 0x00000050,
        })
        DspFlow.connect(dspflow, net, self, 'in_', prefix='in_')
        return self
