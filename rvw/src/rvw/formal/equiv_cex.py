"""Locate a failed closed eqy partition for the existing simulation replayer."""

def model_for_trace(root, trace):
    trace=trace.resolve();root=root.resolve()
    if not trace.is_relative_to(root/'eqy'):
        raise ValueError('equivalence witness must be inside the captured eqy run')
    for directory in trace.parents:
        if directory==root:break
        model=directory/'model/design.il'
        status=directory/'status'
        if model.is_file() and status.is_file():
            if status.read_text().split()[:1]!=['FAIL']:
                raise ValueError('equivalence replay needs a failed native partition')
            return model
    raise ValueError('failed equivalence partition model is missing')
