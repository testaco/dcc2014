from system import system

@system.view(r'^(?P<node_path>.*)\/resource-tree.latex$')
def resource_tree(node_path):
    node = system.node_at_path(node_path)
    with open(system.name + '-resource-tree.latex', 'w') as f:
        node_name = node.name or 'root'
        print >>f, '\\begin{tikzpicture}[align=center]'
        print >>f, '\\tikzstyle{every node} = [draw];'
        print >>f,  '\\node (%(name)s) {%(name_newline)s} [edge from parent fork down]' % { 'name': node_name, 'name_newline': node_name.replace('_', '\\\\') }
        def print_it(i, n):
            d = {
                'name': n.name,
                'name_newline': n.name.replace('_', '\\\\'),
            }
            if len(n.children) == 0:
                print >>f, '    '*i, 'child { node (%(name)s) {%(name_newline)s} }' % d
            else:
                print >>f, '    '*i, 'child { node (%(name)s) {%(name_newline)s}' % d
            for child in n.children.itervalues():
                print_it(i + 1, child)

            if len(n.children) > 0:
                print >>f, '    '*i, '}'

        for child in node.children.itervalues():
            print_it(1, child)
        print >>f, ';'
        print >>f, '\\end{tikzpicture}'
