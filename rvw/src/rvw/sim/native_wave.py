"""Two-state public-port VCD for native model evaluation boundaries."""
from pathlib import Path


class PortWave:
    def __init__(self, path, ports):
        self.stream = Path(path).open('x')
        self.ports = ports
        self.previous = {}
        self.stream.write('$timescale 1ps $end\n$scope module model $end\n')
        for index, (name, (_, width)) in enumerate(ports.items()):
            self.stream.write(f'$var wire {width} p{index} {name} $end\n')
        self.stream.write('$upscope $end\n$enddefinitions $end\n')

    def sample(self, step, read):
        self.stream.write(f'#{step}\n')
        for index, (name, (_, width)) in enumerate(self.ports.items()):
            value = read(name)
            if self.previous.get(name) != value:
                self.stream.write(f'b{value:0{width}b} p{index}\n')
                self.previous[name] = value

    def close(self):
        self.stream.close()
