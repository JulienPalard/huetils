import logging


logger = logging.getLogger()


def illumination(now, sun) -> float:
    """Give the sun illumination.

    0: It's still the night.
    0.x: Partial illumination between night and day or day and night.
    1: It's the day.
    """
    if now < sun["dawn"] or now > sun["dusk"]:
        return 0.0
    if now < sun["sunrise"]:
        return (now - sun["dawn"]).total_seconds() / (
            sun["sunrise"] - sun["dawn"]
        ).total_seconds()
    if now > sun["sunset"]:
        return (
            1
            - (now - sun["sunset"]).total_seconds()
            / (sun["dusk"] - sun["sunset"]).total_seconds()
        )
    return 1


def interpolate(alpha, min_temp, max_temp):
    return (1 - alpha) * min_temp + alpha * max_temp


def test_illumination():
    import astral.sun
    from astral.geocoder import lookup, database
    from datetime import datetime, timezone, timedelta

    def hour(h, m):
        return datetime(2021, 12, 25, h, m, 0).replace(tzinfo=timezone.utc)

    city = lookup("Paris", database())
    sun = astral.sun.sun(city.observer, date=hour(0, 0).date())

    assert illumination(hour(2, 0), sun) == 0
    assert illumination(hour(3, 0), sun) == 0
    assert illumination(hour(7, 10), sun) > 0
    assert illumination(hour(7, 10), sun) < illumination(hour(7, 20), sun)
    assert illumination(hour(7, 20), sun) < illumination(hour(7, 30), sun)
    assert illumination(hour(8, 0), sun) == 1
    assert illumination(hour(9, 0), sun) == 1
    assert illumination(hour(16, 0), sun) < 1
    assert illumination(hour(16, 0), sun) > illumination(hour(16, 10), sun)
    assert illumination(hour(16, 10), sun) > illumination(hour(16, 20), sun)
