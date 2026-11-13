"""Align unspecified FCSR once, before a verified state-neutral instruction."""


def seed(actual, model, platform, *, prior_events=0):
    # Do not infer pre-state from a post-state that FP or CSR work could change.
    # Unsupported references keep strict comparison, including the reset mismatch.
    neutral = {0x13, 0x17, 0x37, 0x33, 0x1b, 0x3b, 0x6f, 0x67, 0x63}
    if (prior_events or actual['order'] != 0 or actual['pc'] != platform.reset_pc
            or actual['trap'] or actual['fd_valid'] or actual['insn'] & 0x7f not in neutral
            or not hasattr(model, 'seed_fcsr')):
        return None
    model.seed_fcsr(actual['fcsr'])
    return dict(order=0, reason='fcsr_reset_unspecified', csr='0x3',
                source='state_before_neutral_instruction', core=hex(actual['fcsr']))
