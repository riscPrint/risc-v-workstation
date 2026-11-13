import pytest
from rvw.cosim.cheri import validate, REFERENCE, REVISION


def test_optional_pinned_hook():
    assert validate(None) is None
    config = dict(repository=REFERENCE, revision=REVISION, capability_bits=128)
    assert validate(config) == config
    with pytest.raises(ValueError, match='pinned'):
        validate(dict(config, revision='master'))
    with pytest.raises(ValueError, match='width'):
        validate(dict(config, capability_bits=129))


def test_selected_cheri_cannot_earn_scalar_match():
    from rvw.cosim.platform import Platform
    from rvw.cosim.checker import check
    platform = Platform.load('boom')
    platform.cheri = dict(repository=REFERENCE, revision=REVISION, capability_bits=128)
    with pytest.raises(ValueError, match='CHERI capability comparison'):
        check('not-read', object(), platform)
