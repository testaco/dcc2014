from myhdl import *

from system import system

def ram(reset,
        addra, dina, pipea, wmodea, blka, wena, clka, douta,
        addrb, dinb, pipeb, wmodeb, blkb, wenb, clkb, doutb,
        width, depth, **kwargs):
    """A ram block."""
    delay = kwargs.get('delay', 3)
    ram = [Signal(intbv(0, min=0, max=2**width-1), delay=delay) for i in xrange(depth)]

    ba = len(douta)
    bb = len(doutb)
    
    if pipea:
        da = Signal(intbv(0, min=0, max=2**ba))
    else:
        da = douta

    if pipeb:
        db = Signal(intbv(0, min=0, max=2**bb))
    else:
        db = doutb

    @always_comb
    def reader():
        da.next = ram[addra]
        db.next = ram[addrb]

    @always(clka.posedge)
    def porta():
        if not blka and not wena:
            ram[addra].next = dina

    @always(clkb.posedge)
    def portb():
        if not blkb and not wenb:
            ram[addrb].next = dinb

    @always(clka.posedge)
    def porta_pipe():
        douta.next = da

    @always(clkb.posedge)
    def portb_pipe():
        doutb.next = db

    instances = (reader, porta, portb)
    if pipea:
        instances = instances + (porta_pipe, )
    if pipeb:
        instances = instances + (portb_pipe, )
    return instances

@system.model
class Ram(object):
    def __init__(self, resetn, clka, clkb, width, depth, **kwargs):
        self._resetn = resetn
        self._clka = clka
        self._clkb = clkb
        self.width = width
        self.depth = depth
        pipe = kwargs.get('pipe', True)
        pipe = 1 if pipe else 0
        self.kwargs = kwargs
        #self.resetn = resetn.signal
        self.addra = Signal(intbv(0)[depth:])
        self.dina = Signal(intbv(0)[width:])
        self.pipea = pipe
        self.wmodea = 0
        self.blka = Signal(bool(1))
        self.wena = Signal(bool(1))
        #self.clka = clka.signal
        self.douta = Signal(intbv(0)[width:])
        self.addrb = Signal(intbv(0)[depth:])
        self.dinb = Signal(intbv(0)[width:])
        self.pipeb = pipe
        self.wmodeb = 0
        self.blkb = Signal(bool(1))
        self.wenb = Signal(bool(1))
        #self.clkb = clkb.signal
        self.doutb = Signal(intbv(0)[width:])

    def signals_dict(self):
        signals = dict(
                #reset=self.resetn,
                addra=self.addra,
                dina=self.dina,
                pipea=self.pipea,
                wmodea=self.wmodea,
                blka=self.blka,
                wena=self.wena,
                #clka=self.clka,
                douta=self.douta,
                addrb=self.addrb,
                dinb=self.dinb,
                pipeb=self.pipeb,
                wmodeb=self.wmodeb,
                blkb=self.blkb,
                wenb=self.wenb,
                #clkb=self.clkb,
                doutb=self.doutb,
                width=self.width,
                depth=self.depth,
        )
        signals.update(self._resetn(name='reset'))
        signals.update(self._clka(name='clka'))
        signals.update(self._clkb(name='clkb'))
        return signals

    def port_a(self, prefix=None, d=None):
        if d:
            return dict([(theirs, getattr(self, mine))
                for mine, theirs in d.iteritems()])
        if prefix is None:
            prefix = ''
        signals = {
            '%saddr' % (prefix,): self.addra,
            '%sdin' % (prefix,): self.dina,
            '%sblk' % (prefix,): self.blka,
            '%swen' % (prefix,): self.wena,
            '%sdout' % (prefix,): self.douta,
        }
        signals.update(self._clka(name='%sclk' % prefix))
        return signals

    def port_b(self, prefix=None):
        if prefix is None:
            prefix = ''
        signals = {
            '%saddr' % (prefix,): self.addrb,
            '%sdin' % (prefix,): self.dinb,
            '%sblk' % (prefix,): self.blkb,
            '%swen' % (prefix,): self.wenb,
            '%sdout' % (prefix,): self.doutb,
        }
        signals.update(self._clkb(name='%sclk' % prefix))
        return signals

    @property
    def instance(self):
        return ram

    @classmethod
    def create_and_connect(cls, parent_path, name, resetn, clka, clkb, width, depth, pipe=True):
        path = lambda node, name: '%s#%s' % (node.path, name)
        self = system.add_node(parent_path, name, 'Ram', { 'width': width, 'depth': depth, 'pipe': pipe })
        system.add_edge('CallAttrEdge',
            path(resetn, 'signals_dict'),
            path(self, 'resetn'))
        system.add_edge('CallAttrEdge',
            path(clka, 'out'),
            path(self, 'clka'))
        system.add_edge('CallAttrEdge',
            path(clkb, 'out'),
            path(self, 'clkb'))
        return self

def fifo(resetn,
         re, rclk, Q, we, wclk, data, full, afull, empty, aempty,
         afval, aeval, wack, dvld, overflow, underflow, rdcnt, wrcnt,
         depth,
         read_clk, read_addr, read_din, read_blk, read_wen, read_dout,
         write_clk, write_addr, write_din, write_blk, write_wen, write_dout):

    wptr = Signal(modbv(0, min=0, max=depth))
    rptr = Signal(modbv(0, min=0, max=depth))

    @always_comb
    def assignments():
        rclk.next = read_clk
        read_addr.next = rptr
        read_wen.next = re
        read_blk.next = not re
        Q.next = read_dout

        wclk.next = write_clk
        write_addr.next = wptr
        write_wen.next = not we
        write_blk.next = not we
        write_din.next = data

        full.next = wptr == modbv(rptr - 1, min=0, max=depth)
        empty.next = wptr == rptr

        #wrcnt.next = modbv(depth - (wptr - rptr), min=0, max=depth)
        #rdcnt.next = modbv(wptr - rptr, min=0, max=depth)

        #afull.next = wrcnt >= afval
        #aempty.next = rdcnt <= aeval


    @always_seq(wclk.posedge, reset=resetn)
    def writer():
        if we:
            if full:
                overflow.next = True
                #raise NotImplementedError, 'overflow'
                wack.next = False
            else:
                wptr.next = wptr + 1
                #wcnt.next = wcnt - 1   TODO
                wack.next = True
                overflow.next = False
        else:
            overflow.next = False
            wack.next = False

    @always_seq(rclk.posedge, reset=resetn)
    def reader():
        if re:
            if empty:
                underflow.next = True
                #raise NotImplementedError, 'underflow'
                dvld.next = False
            else:
                rptr.next = rptr + 1
                dvld.next = True
                underflow.next = False
        else:
            dvld.next = False
            underflow.next = False

    return assignments, writer, reader

@system.model
class Fifo(object):
    def __init__(self, resetn, write_port, read_port, width, depth):
        self._resetn = resetn
        self._write_port = write_port
        self._read_port = read_port
        self.width = width
        self.depth = depth

        self.re = Signal(bool(False))
        self.rclk = Signal(bool(False))
        self.Q = Signal(intbv(0)[width:])
        self.we = Signal(bool(False))
        self.wclk = Signal(bool(False))
        self.data = Signal(intbv(0)[width:])
        self.full = Signal(bool(False))
        self.afull = Signal(bool(False))
        self.empty = Signal(bool(True))
        self.aempty = Signal(bool(True))
        self.afval = Signal(intbv(0, min=0, max=depth))
        self.aeval = Signal(intbv(0, min=0, max=depth))
        self.wack = Signal(bool(False))
        self.dvld = Signal(bool(False))
        self.overflow = Signal(bool(False))
        self.underflow = Signal(bool(False))
        self.rdcnt = Signal(intbv(0, min=0, max=depth))
        self.wrcnt = Signal(intbv(depth - 1, min=0, max=depth))

    def write_port(self, prefix=None):
        signals = {
                '%swe' % (prefix, ): self.we,
                '%swclk' % (prefix, ): self.wclk,
                '%sdata' % (prefix, ): self.data,
                '%sfull' % (prefix, ): self.full,
                '%safull' % (prefix, ): self.afull,
                '%swack' % (prefix, ): self.wack,
                '%soverflow' % (prefix, ): self.overflow,
                '%swrcnt' % (prefix, ): self.wrcnt,
        }
        return signals

    def read_port(self, prefix=None):
        signals = {
                '%sre' % (prefix, ): self.re,
                '%srclk' % (prefix, ): self.rclk,
                '%sQ' % (prefix, ): self.Q,
                '%sempty' % (prefix, ): self.empty,
                '%saempty' % (prefix, ): self.aempty,
                '%sdvld' % (prefix, ): self.dvld,
                '%sunderflow' % (prefix, ): self.underflow,
                '%srdcnt' % (prefix, ): self.rdcnt,
        }
        return signals


    def signals_dict(self, prefix=None):
        if prefix is None:
            prefix = ''
        signals = {
                '%sre' % (prefix, ): self.re,
                '%srclk' % (prefix, ): self.rclk,
                '%sQ' % (prefix, ): self.Q,
                '%swe' % (prefix, ): self.we,
                '%swclk' % (prefix, ): self.wclk,
                '%sdata' % (prefix, ): self.data,
                '%sfull' % (prefix, ): self.full,
                '%safull' % (prefix, ): self.afull,
                '%sempty' % (prefix, ): self.empty,
                '%saempty' % (prefix, ): self.aempty,
                '%safval' % (prefix, ): self.afval,
                '%saeval' % (prefix, ): self.aeval,
                '%saeval' % (prefix, ): self.aeval,
                '%swack' % (prefix, ): self.wack,
                '%sdvld' % (prefix, ): self.dvld,
                '%sunderflow' % (prefix, ): self.underflow,
                '%soverflow' % (prefix, ): self.overflow,
                '%srdcnt' % (prefix, ): self.rdcnt,
                '%swrcnt' % (prefix, ): self.wrcnt,
                'depth': self.depth,
        }
        signals.update(self._resetn(name='%sresetn' % prefix))
        signals.update(self._write_port())
        signals.update(self._read_port())
        return signals
    
    @property
    def instance(self):
        return fifo

    @classmethod
    def create_and_connect(cls, parent_path, name, resetn, wclk, rclk, width, depth):
        path = lambda node, name: '%s#%s' % (node.path, name)
        self = system.add_node(parent_path, name, 'Fifo', {'width': width, 'depth': depth})
        ram = Ram.create_and_connect(self.path, 'ram', resetn, wclk, rclk, width, depth, pipe=False)
        system.add_edge('CallAttrEdge',
            path(resetn, 'signals_dict'),
            path(self, 'resetn'))
        system.add_edge('CallAttrEdge',
            path(ram, 'port_a'),
            path(self, 'write_port'),
            dict(prefix='write_'))
        system.add_edge('CallAttrEdge',
            path(ram, 'port_b'),
            path(self, 'read_port'),
            dict(prefix='read_'))
        return self

