"""Incremental acyclic relation for bounded candidate prefixes."""
class OrderGraph:
    def __init__(self, edges=()):
        self.adj = {}
        if not self.add(edges):
            raise ValueError('cyclic initial order')

    def copy(self):
        graph = OrderGraph()
        graph.adj = {a: set(bs) for a, bs in self.adj.items()}
        return graph

    def add(self, edges):
        for a, b in edges:
            if b in self.adj.get(a, ()):
                continue
            todo, seen = [b], set()
            while todo:
                node = todo.pop()
                if node == a:
                    return False
                if node not in seen:
                    seen.add(node)
                    todo.extend(self.adj.get(node, ()))
            self.adj.setdefault(a, set()).add(b)
        return True
