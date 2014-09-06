from myhdl import ResetSignal, Signal, intbv

from system import system

@system.model
class Reset(object):
    def __init__(self, **kwargs):
        self.signal = ResetSignal(0, 0, **kwargs)

    def signals_dict(self, name):
        return { name: self.signal }

    @classmethod
    def create_and_connect(cls, parent_path, name, **kwargs):
        return system.add_node(parent_path, name, 'Reset', kwargs)


@system.model
class Led(object):
    def __init__(self, **kwargs):
        self.signal = Signal(bool(False))

    def signals_dict(self, prefix=None, name=None):
        if name:
            return { name: self.signal }
        if prefix is None:
            prefix = ''
        return { '%sled' % prefix: self.signal }

    @classmethod
    def create_and_connect(cls, parent_path, name, **kwargs):
        return system.add_node(parent_path, name, 'Led', kwargs)

@system.model
class Slider(object):
    def __init__(self, min, max, step, default):
        self.val = Signal(intbv(int(default), min=int(min), max=int(max)))
        self.step = step

    def signals_dict(self):
        return self.val

    @classmethod
    def create(cls, parent_path, name, min, max, step, default):
        self = system.add_node(parent_path, name, 'Slider', {
                'min': min,
                'max': max,
                'step': step,
                'default': default,
                })
        return self

    @classmethod
    def connect(cls, self, to, to_port):
        path = lambda node, name: '%s#%s' % (node.path, name)
        print self, to, to_port
        system.add_edge('CallAttrEdge',
            path(self, 'signals_dict'),
            path(to, to_port))
