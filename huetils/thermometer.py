"""Like a thermometer, this script changes the hue of a light to
reflect the outdoor temperature.

Better run it in an hourly crontab.
"""

import argparse
from subprocess import run, PIPE
from datetime import datetime, timezone
from phue import Bridge
from astral.geocoder import lookup, database
import astral.sun
from huetils.utils import illumination, interpolate


def between(mini, maxi, color_start, color_end, current):
    irange = abs(maxi - mini)
    orange = color_start - color_end
    return int(color_start + orange * (mini - current) / irange)


def degree_c_to_hue_color(temp):
    """Maps celcius degress from -10°C → 40°C to a Philips hue color.
    Gives: 40°C -> purple (56100)
           30°C -> red (0 or 65280)
           20°C -> orange (12750 / 2)
           10°C -> yellow (12750)
            0°C -> green (25500)
          -10°C -> blue (46920)

    From -10 to 30: -1173 × temp + 35190
    From 30 to 40: -918 × temp + 92820

    Computed with:

       a = (-10, 46920)
       b = (40, 0)
       slope = (a[1] - b[1]) / (a[0] - b[0])
       y_intercept = 46920 - slope * -10  # b = y - mx
    """
    if temp < -10:
        return 46920
    if temp < 0:
        return between(-10, 0, 46920, 25500, temp)
    if temp < 10:
        return between(0, 10, 25500, 12750, temp)
    if temp < 30:
        return between(10, 30, 12750, 0, temp)
    if temp < 40:
        return between(30, 40, 65280, 56100, temp)
    return 56100


def parse_args():
    parser = argparse.ArgumentParser(description="Bind temperature to hue color")
    parser.add_argument("--hue-bridge", help="Bridge IP address", required=True)
    parser.add_argument("--light", required=True)
    parser.add_argument(
        "--weather", help="Weather station (passed to `weather`).", required=True
    )
    parser.add_argument(
        "--city", help="City (as used by astral library).", required=True
    )
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    bridge = Bridge(args.hue_bridge)
    bridge.connect()
    light = bridge.get_light(args.light)

    if not light["state"]["on"]:
        bridge.set_light(args.light, "on", True)
    bridge.set_light(args.light, "sat", 255)
    city = lookup(args.city, database())
    now = datetime.now(timezone.utc)
    sun = astral.sun.sun(city.observer, date=now.date())
    meteo = run(
        ["weather", "--headers=temperature", "-m", "-q", args.weather],
        stdout=PIPE,
        check=True,
        encoding="UTF-8",
    ).stdout
    degree = int(meteo.split()[1])
    if args.verbose:
        print(degree)
    color = degree_c_to_hue_color(degree)
    bridge.set_light(args.light, "hue", color)
    bridge.set_light(args.light, "bri", interpolate(illumination(now, sun), 0, 255))


if __name__ == "__main__":
    main()
