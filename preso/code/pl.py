# Some helpers for manipulating strings
import string

# Easy manipulation of files as strings
from cStringIO import StringIO

class Token(object):
    BEGIN = 0
    END = 1
    QUOTE = 2
    ATOM = 3
    TYPES = ['begin', 'end', 'quote', 'atom',]
    def __init__(self, t, v=None):
        self.t = t
        self.value = v

    def __repr__(self):
        if self.t == self.ATOM:
            return '<Token %s("%s")>' % (self.TYPES[self.t], self.value)
        elif self.t in (self.BEGIN, self.END, self.QUOTE):
            return '<Token %s>' % self.TYPES[self.t]

def lex(f):
    whitespace = set(string.whitespace)
    tmp = []
    reading = type(tmp)

    for c in f.read():
        if reading == list:
            if c == '(':
                yield Token(Token.BEGIN)
            elif c == ')':
                if len(tmp) > 0:
                    yield Token(Token.ATOM, ''.join(tmp))
                    tmp = []
                yield Token(Token.END)
            elif c == '\'':
                yield Token(Token.QUOTE)
            elif c in whitespace:
                if len(tmp) > 0:
                    yield Token(Token.ATOM, ''.join(tmp))
                    tmp = []
            else:
                tmp.append(c)
    if len(tmp) > 0:
        yield Token(Token.ATOM, ''.join(tmp))

from collections import namedtuple
Symbol = namedtuple('Symbol', 'name')

def parse(tokens):
    def atom(value):
        try:
            return int(value)
        except:
            try:
                return float(value)
            except:
                return Symbol(value)

    def _parse(itertokens, current, in_quote=False):
        while True:
            try:
                token = itertokens.next()
            except StopIteration:
                break

            if token.t == Token.BEGIN:
                child = []
                current.append(child)
                _parse(itertokens, child)
            elif token.t == Token.END:
                break
            elif token.t == Token.QUOTE:
                child = [atom('quote')]
                current.append(child)
                _parse(itertokens, child, True)
            elif token.t == Token.ATOM:
                current.append(atom(token.value))
            else:
                raise NotImplementedError

            if in_quote:
                break

    ast = []        
    _parse(iter(tokens), ast)
    return ast

def evaluate(ast, env=None):
    class Environment(dict):
        def __init__(self, outer=None):
            self.outer = outer or {}

        def __getitem__(self, key):
            if key in self:
                return super(Environment, self).__getitem__(key)
            else:
                return self.outer[key]

    class Procedure(object):
        def __init__(self, arg_names, expr, env):
            self.env = env
            self.arg_names = [a.name for a in arg_names]
            self.expr = expr

        def __call__(self, *args):
            callenv = Environment(self.env)
            callenv.update(zip(self.arg_names, args))
            return _evaluate(self.expr, callenv)

    def _evaluate(x, env):
        if type(x) == Symbol:
            return env[x.name]
        elif type(x) != list:
            return x
        else:
            if len(x) == 0:
                return []
            elif x[0] == Symbol('quote'):
                return x[1]
            elif x[0] == Symbol('atom?'):
                a = _evaluate(x[1], env)
                return (type(a) == list and len(a) == 0) or (type(a) != list)
            elif x[0] == Symbol('cond'):
                for p, e in x[1:]:
                    if _evaluate(p, env):
                        return _evaluate(e, env)
            elif x[0] == Symbol('lambda'):
                return Procedure(x[1], x[2], env)
            elif x[0] == Symbol('label'):
                env[x[1].name] = _evaluate(x[2], env)
                return []
            elif x[0] == Symbol('eval'):
                newenv = Environment(env)
                newenv.update(dict([(a[0].name, a[1]) for a in _evaluate(x[2], env)]))
                return _evaluate(x[1], newenv)
            elif x[0] == Symbol('begin'):
                result = []
                for i in x[1:]:
                    result = _evaluate(i, env)
                return result
            elif x[0] == Symbol('node'):
                print 'node', _evaluate(x[1], env), _evaluate(x[2], env), \
                    dict([(a.name, b) for a, b in _evaluate(x[3], env)])
                if len(x) == 5:
                    for c in x[4]:
                        _evaluate(c, env)
                return []
            elif x[0] == Symbol('edge'):
                print 'edge'
                return []
            else:
                a = [_evaluate(i, env) for i in x]
                try:
                    if type(a[0]) == list and len(a[0]) == 0:
                        return []
                    elif type(a[0]) == list and a[0][0] == Symbol('lambda'):
                        a[0] = _evaluate(a[0], env)
                    return a[0](*a[1:])
                except:
                    print a
                    raise
        raise NotImplementedError

    import operator as op
    env = env or Environment()
    env.update(
    {'+':op.add, '-':op.sub, '*':op.mul, '/':op.div, 'not':op.not_,
    '>':op.gt, '<':op.lt, '>=':op.ge, '<=':op.le, '=':op.eq, 
    'equal?':op.eq, 'eq?':op.is_, 'length':len, 'cons':lambda x,y:[x]+y,
    'car':lambda x:x[0],'cdr':lambda x:x[1:], 'append':op.add,  
    'list':lambda *x:list(x), 'list?': lambda x:isa(x,list), 
    'null?':lambda x:x==[], 'symbol?':lambda x: isa(x, Symbol)})
    return _evaluate(ast, env), env

from pprint import pprint
class VirtualMachine(object):
    def __init__(self):
        self.stack = []

    def read(self, f):
        tokens = [t for t in lex(f)]
        self.ast = parse(tokens)
        #pprint(self.ast)

    def evaluate(self):
        env = {}
        for expr in self.ast:
            result, env = evaluate(expr, env)
            self.stack.append(result)
        #pprint(env)

    def pop(self):
        return self.stack.pop() if len(self.stack) else None

def lprint(obj):
    if type(obj) == list:
        return '(%s)' % ' '.join([lprint(l) for l in obj])
    elif obj == True:
        return 't'
    elif obj == False:
        return '()'
    elif type(obj) == Symbol:
        return obj.name
    else:
        return str(obj)

vm = VirtualMachine()
examples = (
    ("(quote a)", "a"),
    ("'a", "a"),
    ("(quote (a b c))", "(a b c)"),
    ("(atom? 'a)", "t"),
    ("(atom? '(a b c))", "()"),
    ("(atom? '())", "t"),
    ("(atom? (atom? 'a))", "t"),
    ("(atom? '(atom? 'a))", "()"),
    ("(equal? 'a 'a)", "t"),
    ("(equal? 'a 'b)", "()"),
    ("(equal? '() '())", "t"),
    ("(car '(a b c))", "a"),
    ("(cdr '(a b c))", "(b c)"),
    ("(cons 'a '(b c))", "(a b c)"),
    ("(cons 'a (cons 'b (cons 'c '())))", "(a b c)"),
    ("(car (cons 'a '(b c)))", "a"),
    ("(cdr (cons 'a '(b c)))", "(b c)"),
    ("(cond ((equal? 'a 'b) 'first) \
        ((atom? 'a) 'second))", "second"),
    ("((lambda (y) (cons y '(b))) 'a)", "(a b)"),
    ("((lambda (x y) (cons x (cdr y))) \
        'z \
        '(a b c))", "(z b c)"),
    ("((lambda (f) (f '(b c))) \
        '(lambda (x) (cons 'a x)))", "(a b c)"),
    ("""(label subst (lambda (x y z)
                       (cond ((atom? z)
                              (cond ((equal? z y) x)
                                    ('t z)))
                             ('t (cons (subst x y (car z))
                                       (subst x y (cdr z)))))))
        (subst 'm 'b '(a b (a b c) d))""", "(a m (a m c) d)"),
    ("""(label add (lambda (a b) (+ a b)))(add 2 2)""", "4"),
    ("""(eval (+ x y) '((y 2) (x 2)))""", "4"),
)
for example, expected in examples:
    input_file = StringIO(example)
    vm.read(input_file)
    print '>>>', lprint(vm.ast)
    vm.evaluate()
    actual = lprint(vm.pop())
    print '>>>', example
    print 'Ex:', expected
    print 'Ac:', actual
    print
    assert actual == expected

input_file = open('project2.sexpr')
vm.read(input_file)
vm.evaluate()
print lprint(vm.pop())
