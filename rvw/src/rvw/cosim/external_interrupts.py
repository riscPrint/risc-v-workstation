"""Declared C2 external-interrupt evidence. Values come from DUT inputs and buses."""
SCHEMA = 'rvw.external-interrupts/1'
KINDS = {'pins', 'source', 'mmio', 'ack', 'taken'}


def declaration(value):
    if not isinstance(value, dict) or value.get('schema') != SCHEMA:
        raise ValueError('invalid external_interrupts declaration')
    # Model configuration and stimulus are project data. Consumers must bind them
    # before they use these records as reference inputs.
    return value


def validate(event, header, sequence, before_order):
    from .trace import hexnum
    declaration(header.get('external_interrupts'))
    if (type(event.get('seq')) is not int or event['seq'] != sequence
            or type(event.get('before_order')) is not int or event['before_order'] != before_order):
        raise ValueError('external interrupt sequence or retirement boundary differs')
    kind = event.get('kind')
    if kind not in KINDS:
        raise ValueError('invalid external interrupt evidence kind')
    if kind == 'pins':
        hexnum(event['levels'], header['xlen'])
    elif kind == 'source':
        if type(event.get('source')) is not int or event['source'] <= 0 or type(event.get('level')) is not bool:
            raise ValueError('invalid interrupt source level')
    elif kind == 'taken':
        cause = hexnum(event['cause'], header['xlen'])
        if cause >> (header['xlen'] - 1) != 1:
            raise ValueError('taken evidence must name an interrupt')
    else:
        hexnum(event['address'], header['xlen'])
        hexnum(event['value'], header['xlen'])
        if type(event.get('bytes')) is not int or event['bytes'] not in (1, 2, 4, 8) or event['bytes'] > header['xlen'] // 8:
            raise ValueError('invalid external access width')
        if hexnum(event['value'], header['xlen']) >= 1 << (event['bytes'] * 8):
            raise ValueError('external value exceeds access width')
        if kind == 'mmio' and type(event.get('write')) is not bool:
            raise ValueError('external MMIO needs a read/write direction')
        if kind == 'ack' and (type(event.get('step')) is not int or event['step'] <= 0):
            raise ValueError('external acknowledgement needs a positive step')
