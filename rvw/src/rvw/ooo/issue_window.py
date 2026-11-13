"""Age-ordered line reuse for a compacting issue queue."""


class IssueWindow:
    def __init__(self, entries, width):
        self.capacity = entries // width
        self.width = width
        self.lines = []
        self.current = None

    def advance(self, cycle):
        # A line remains busy until all wakeups arrive, even after issue.
        while self.lines and all(e.done is not None and e.done < cycle for e in self.lines[0]):
            self.lines.pop(0)
        self.current = None

    def full(self):
        return (self.current is None or len(self.current) >= self.width) and len(self.lines) >= self.capacity

    def append(self, entry):
        if self.current is None or len(self.current) >= self.width:
            self.current = []
            self.lines.append(self.current)
        self.current.append(entry)

    def drop(self, entries):
        self.lines = [[e for e in line if e not in entries] for line in self.lines]
        self.current = None
