"""Separate missing predictions from incorrect target addresses."""


def classify(*, taken, predicted_taken, btb_hit, predicted_target, target):
    if not taken:
        return 'not-taken'
    if btb_hit is False:
        return 'btb-miss'
    if predicted_taken is False:
        return 'not-predicted'
    if predicted_taken is None or predicted_target is None:
        return 'unknown'
    return 'correct' if predicted_target == target else 'wrong-target'
