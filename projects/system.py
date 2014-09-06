import json
import os.path

from collections import OrderedDict
class SystemNode(object):
    def __init__(self, system, cls, kwargs, name, parent):
        self._container = None
        self._created = False
        self.cls = cls
        self.kwargs = kwargs or {}
        self.name = name
        self.parent = parent
        self.children = OrderedDict()
        self.inputs = OrderedDict()
        self.outputs = OrderedDict()

    @property
    def container(self):
        if not self._created:
            self._created = True
            if self.cls == 'NoneType':
                self._container = None
            else:
                cls = system.models[self.cls]
                callargs = dict(self.inputs)
                callargs.update(self.kwargs)
                print cls, callargs
                self._container = cls(**callargs)
        return self._container

    @property
    def path(self):
        path = [self.name]
        parent = self.parent
        while parent:
            path.insert(0, parent.name)
            parent = parent.parent
        return '/'.join(path)

system = None

class System(object):
    """The System is the top-level instance that everything hangs off of.
    
    :param name: A unique name for this system; typically __name__ of your
                 package.
    """

    # The type of class that makes up the system tree.
    node_class = SystemNode

    def __init__(self, name):
        global system
        system = self
        self.name = name

        # Models are objects stored in a dict.
        self.models = {}

        # Views are tuples of (regular expression object, view method, and
        # default kwargs.
        self.views = []

        # Methods to load system.
        self.load_list = []

        # Methods to execute the system.
        self.execute_list = []

        # This is the database.
        self.root = self.node_class(self, 'OperatingSystem', None, '', None)

    def model(self, cls, name=None):
        """Register a model with the system."""
        if name is None:
            name = cls.__name__
        self.models[name] = cls
        return cls

    def node_at_path(self, path):
        paths = path.split('/')
        i = self.root
        for p in paths:
            if p == '' or p == '.':
                continue
            elif p == '..':
                i = i.parent
            else:
                i = i.children[p]
        return i

    def traverse(self, root_path, f, include_root=True):
        def _traverse(n, f, call_on):
            if call_on:
                f(n)
            for c in n.children.itervalues():
                _traverse(c, f, True)
        n = self.node_at_path(root_path)
        _traverse(n, f, include_root)

    def add_node(self, parent_path, name, cls, d=None):
        parent = self.node_at_path(parent_path)
        container_cls = self.models[cls]
        node = self.node_class(self, cls, d, name, parent)
        parent.children[name] = node
        return node
    
    def add_edge(self, cls, f, to, d=None):
        d = d or {}
        edge_cls = self.models[cls]
        edge = edge_cls(self, f, to, d)
        return edge
    
    def register_load(self, func):
        self.load_list.append(func)
        return func

    def load(self): 
        for f in self.load_list:
            f()

    def register_execute(self, func):
        self.execute_list.append(func)
        return func

    def execute(self): 
        for f in self.execute_list:
            f()

    def view(self, regexp, **kwargs):
        """Register a view and controller with the system."""
        import re
        def decorator(func):
            self.views.append((re.compile(regexp), func, kwargs))
        return decorator

    def dispatch(self, uri):
        for regexp, func, kwargs in self.views:
            m = regexp.search(uri)
            if m:
                callkwargs = kwargs
                callkwargs.update(m.groupdict())
                return func(**callkwargs)
        raise NotImplementedError, 'Unknown view for %s' % uri

def run():
    print
    print 'Loading the system'
    print

    system.load()

    print
    print '-----------------'
    print 'Dumping the system'
    print

    def print_it(x):
        if x.path == '':
            return
        try:
            print x.path#, x.container
        except:
            print 'can\'t make %s' % x.path
            raise

    def print_inputs(x):
        for n, i in x.inputs.iteritems():
            if type(i) == list:
                for j in i:
                    print x.path, n, j.from_node.path, '->', j.to_node.path, j.kwargs
            else:
                print x.path, n, i.from_node.path, '->', i.to_node.path, i.kwargs

    def traverse(n, f):
        f(n)
        for c in n.children.itervalues():
            traverse(c, f)

    traverse(system.root, print_it)
    traverse(system.root, print_inputs)

    system.execute()

    print
    print "----------------"
    print 'Storing the system'
    print

    def store_node(node):
        if node.path == '':
            return
        row = {
            '__class__': node.cls,
            'name': node.name,
            'parent': node.parent.path,
        }
        row.update(node.kwargs)
        print json.dumps(['n', row])

    def store_edges(node):
        for n, e in node.inputs.iteritems():
            if type(e) == list:
                for i in e:
                    row = i.__getstate__()
                    print json.dumps(['e', row])
            else:
                row = e.__getstate__()
                print json.dumps(['e', row])

    traverse(system.root, store_node)
    traverse(system.root, store_edges)
