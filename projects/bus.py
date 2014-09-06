from math import log, ceil
from myhdl import *

from system import system

@system.model
class BusMatrix(object):
    def __init__(self, resetn, clk, masters, slaves, address_mask):
        self.resetn = resetn
        self.clk = clk
        self.masters = masters
        self.slaves = slaves
        self.address_mask = address_mask
        self.locked = False
    
    def interface(self):
        return self

    def reset(self):
        if type(self.slaves) == list:
            for slave in self.slaves:
                yield slave().reset()
        else:
            yield self.slaves().reset()

    def delay(self, n):
        if type(self.slaves) == list:
            for slave in self.slaves:
                yield slave().delay(n)
        else:
            yield self.slaves().delay(n)
    
    def _lookup_slave(self, addr):
        if type(self.slaves) == list:
            slave_id = (addr & ~self.address_mask) >> \
                int(ceil(log(self.address_mask + 1, 2)))
            slave = self.slaves[slave_id]
            return slave()
        else:
            return self.slaves()

    def transmit(self, addr, data):
        slave = self._lookup_slave(addr)
        #print 'bus.transmit', hex(addr), hex(data)
        yield slave.transmit(addr, data)

    def receive(self, addr):
        slave = self._lookup_slave(addr)
        yield slave.receive(addr)
        self.rdata = slave.rdata
        #print 'bus.receive', hex(addr), hex(self.rdata)

    @classmethod
    def create(cls, parent_path, name, resetn, clk, duration, address_mask):
        path = lambda node, name: '%s#%s' % (node.path, name)
        self = system.add_node(parent_path, name, 'BusMatrix', {
            'address_mask': address_mask })
        system.add_edge('CallAttrEdge',
            path(resetn, 'signals_dict'),
            path(self, 'resetn'),
            dict(name='resetn'))
        system.add_edge('CallAttrEdge',
            path(clk, 'out'),
            path(self, 'clk'),
            dict(name='clk'))
        return self

@system.model
class Apb3Bus(object):
    def __init__(self, resetn, clk, **kwargs):
        self.resetn = resetn
        self.clk = clk
        self.paddr = Signal(intbv(0, 0, 2**32))
        self.psel = Signal(bool(0))
        self.penable = Signal(bool(0))
        self.pwrite = Signal(bool(1))
        self.pwdata = Signal(intbv(0, 0, 2**32))
        self.pready = Signal(bool(1))
        self.prdata = Signal(intbv(0, 0, 2**32))
        self.pslverr = Signal(bool(0))
        self.kwargs = kwargs
        self.rdata = None

    def signals_dict(self, prefix=None, port=None):
        if prefix is None:
            prefix = ''
        sigs = {
            '%spaddr' % prefix: self.paddr,
            '%spsel' % prefix: self.psel,
            '%spenable' % prefix: self.penable,
            '%spwrite' % prefix: self.pwrite,
            '%spwdata' % prefix: self.pwdata,
            '%spready' % prefix: self.pready,
            '%sprdata' % prefix: self.prdata,
            '%spslverr' % prefix: self.pslverr,
        }
        sigs.update(self.resetn(name='%spresetn' % prefix))
        sigs.update(self.clk(name='%spclk' % prefix))
        return sigs

    def interface(self):
        self.duration = int(1e9/10e6) #self.kwargs['duration']
        self.presetn = self.resetn()['presetn']
        self.pclk = self.clk()['pclk']
        return self

    def debug(self, msg):
        if self.kwargs.get('verbose', False):
            print msg
        
    def reset(self):
        """Reset the bus."""

        self.debug('-- Resetting --')
        self.presetn.next = True
        yield delay(self.duration)
        self.presetn.next = False
        yield delay(self.duration)
        self.presetn.next = True

        self.debug('-- Reset --')

    def transmit(self, addr, data):
        """Transmit from master to slave.
        
        :param addr: The address to write to
        :param data: The data to write
        :raises Apb3TimeoutError: If slave doesn't set ``pready`` in time
        """
        assert not addr & 3  # Must be word aligned

        timeout = self.kwargs.get('timeout') or 5 * self.duration

        self.debug('-- Transmitting addr=%s data=%s --' % (hex(addr), hex(data)))
        self.debug('TX: start')
        self.pclk.next = True
        self.paddr.next = intbv(addr)
        self.pwrite.next = True
        self.psel.next = True
        self.pwdata.next = intbv(data)
        yield delay(self.duration // 2)

        self.pclk.next = False
        yield delay(self.duration // 2)

        self.debug('TX: enable')
        self.pclk.next = True
        self.penable.next = True
        yield delay(self.duration // 2)

        timeout_count = 0
        while not self.pready:
            self.debug('TX: wait')
            timeout_count += self.duration
            if timeout_count > timeout:
                raise Apb3TimeoutError
            self.pclk.next = False
            yield delay(self.duration // 2)
            self.pclk.next = True
            yield delay(self.duration // 2)

        self.pclk.next = False
        yield delay(self.duration // 2)

        self.debug('TX: stop')
        self.pclk.next = True
        self.pwrite.next = False
        self.psel.next = False
        self.penable.next = False
        yield delay(self.duration // 2)

        self.pclk.next = False
        yield delay(self.duration // 2)

    def receive(self, addr, assert_equals=None):
        """Receive from slave to master.
        
        :param addr: The address to read from
        :returns: Nothing, but sets ``self.rdata`` to the received data.
        :raises Apb3TimeoutError: If slave doesn't set ``pready`` in time
        """
        assert not addr & 3  # Must be word aligned
        timeout = self.kwargs.get('timeout') or 5 * self.duration

        self.debug('-- Receiving addr=%s --' % (hex(addr),))
        self.debug('RX: start')
        self.pclk.next = True
        self.paddr.next = intbv(addr)
        self.pwrite.next = False
        self.psel.next = True
        yield delay(self.duration // 2)
        self.pclk.next = False
        yield delay(self.duration // 2)

        self.debug('RX: enable')
        self.pclk.next = True
        self.penable.next = True
        yield delay(self.duration // 2)

        timeout_count = 0
        while not self.pready:
            self.debug('RX: wait')
            timeout_count += self.duration
            if timeout_count > timeout:
                raise Apb3TimeoutError
            self.pclk.next = False
            yield delay(self.duration // 2)
            self.pclk.next = True
            yield delay(self.duration // 2)

        self.pclk.next = False
        yield delay(self.duration // 2)

        self.debug('RX: data=%s' % (hex(self.prdata),))
        rdata = self.prdata
        self.rdata = self.prdata
        if assert_equals is not None:
            assert self.prdata == assert_equals, 'Got %s, expected %s' % (hex(self.prdata), hex(assert_equals))
        yield delay(self.duration // 2)

        self.debug('RX: stop')
        self.pclk.next = True
        self.psel.next = False
        self.penable.next = False
        yield delay(self.duration // 2)

        self.pclk.next = False
        yield delay(self.duration // 2)

    def delay(self, cycles):
        """Delay the bus a number of cycles."""
        for i in xrange(cycles):
            self.pclk.next = True
            yield delay(self.duration // 2)
            self.pclk.next = False
            yield delay(self.duration // 2)
    
    @classmethod
    def create(cls, parent_path, name, master, duration=None, verbose=False):
        path = lambda node, name: '%s#%s' % (node.path, name)
        self = system.add_node(parent_path, name, 'Apb3Bus', {'duration': duration, 'verbose': verbose})
        system.add_edge('CallAttrEdge',
            path(master, 'resetn'),
            path(self, 'resetn'),
            dict(name='presetn'))
        system.add_edge('CallAttrEdge',
            path(master, 'clk'),
            path(self, 'clk'),
            dict(name='pclk'))
        system.add_edge('CallAttrEdge',
            path(self, 'interface'),
            path(master, 'slaves'))
        return self
    
    @classmethod
    def connect_slave(cls, self, slave, prefix=None):
        path = lambda node, name: '%s#%s' % (node.path, name)
        system.add_edge('CallAttrEdge',
            path(self, 'signals_dict'),
            path(slave, 'bus'),
            dict(prefix=prefix))
        return self
