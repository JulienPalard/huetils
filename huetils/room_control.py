"""Control a living room.

python hue.py Paris --hue-bridge 10.0.0.7 --sensors 'Salon Entrée' 'Salon Four' 'Salon' 'Salon Fenetre' 'Salon Frigo' --lights 'Salon 1-1' 'Salon 1-2' 'Salon 1-3' 'Salon 1-4' 'Salon 1-5' 'Salon 2-1' 'Salon 2-2' 'Salon 2-3' 'Salon 2-4' 'Salon 2-5' 'Cuisine'
"""
import sys
import argparse
import logging
from datetime import datetime, timezone, timedelta
from subprocess import run, PIPE

from astral.geocoder import lookup, database
import astral.sun
from phue import Bridge
from tabulate import tabulate
from huetils.utils import illumination, interpolate

logger = logging.getLogger()

PERIOD = 10  # in minutes, duration between two start of the script.


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("city", help="City name, like 'Paris'.")
    parser.add_argument("--hue-bridge", help="Hue Bridge IP address.")
    parser.add_argument(
        "--only-switchoff",
        help="Good for bedrooms: "
        "it handle powering off the lights, but not powering them on.",
        action="store_true",
    )
    parser.add_argument("--sensors", nargs="*", help="Hue sensors to watch.")
    parser.add_argument("--lights", nargs="*", help="Hue lights to change.")
    parser.add_argument(
        "--now",
        help="Simulate a specific time (like 2021-12-03T23:00:00) for test purposes.",
    )
    parser.add_argument(
        "--list-sensors", help="List sensors and exit.", action="store_true"
    )
    parser.add_argument(
        "--list-lights", help="List lights and exit.", action="store_true"
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser.parse_args()


def list_sensors(bridge):
    """List all sensors ordered by last push.

    So it's easy for a human to build a --sensors from this."""
    table = []
    for sensor in bridge.sensors:
        table.append((sensor.name, sensor.state["lastupdated"]))
    print(tabulate(sorted(table, key=lambda line: line[1], reverse=True)))


def list_lights(bridge):
    """List all lights by group.

    So it's easy for a human to build a --lights from this."""
    table = []
    reverse_group = {}
    for group in bridge.groups:
        for light in group.lights:
            reverse_group[light.name] = group.name
    for light in bridge.lights:
        table.append((light.name, reverse_group.get(light.name, "")))
    print(tabulate(sorted(table, key=lambda line: line[1], reverse=True)))


def sensor_pressed_not_long_ago(bridge, sensors_to_watch):
    """Watch sensors, tell if one of them has been pressed."""
    now = datetime.now(timezone.utc)
    for sensor in bridge.sensors:
        if sensor.name not in sensors_to_watch:
            continue
        pressed = datetime.fromisoformat(sensor.state["lastupdated"] + "+00:00")
        elapsed_since_pressed = now - pressed
        if elapsed_since_pressed < timedelta(minutes=60):
            logging.info("Sensor %s pressed not long ago...", sensor.name)
            return True


def poweroff_lights(bridge, lights):
    """Slowly power off given lights."""
    logger.info("Need to power off lights %s", lights)
    for light in lights:
        if not light.on:
            logger.info("Light %s already off.", light.name)
            continue
        if light.brightness <= 1:
            logger.info("Light %s is at lowest brightness, powering off.", light.name)
            light.on = False
        else:
            logger.info(
                "Light %s is at bri=%s, will slowly dim down",
                light.name,
                light.brightness,
            )
            bridge.set_light(light.light_id, "bri", 0, transitiontime=PERIOD * 60 * 10)


def poweron_lights(bridge, lights, illum):
    """Slowly power on given lights."""
    target = int(interpolate(illum, 255, 0))
    for light in lights:
        if not light.on:
            logger.info("Light %s is off, powering on.", light.name)
            light.on = True
            light.brightness = 0
        logger.info(
            "Light %s is at bri=%s, will slowly dim to %s",
            light.name,
            light.brightness,
            target,
        )
        bridge.set_light(light.light_id, "bri", target, transitiontime=PERIOD * 60 * 10)


def set_lights_brightness(bridge, now, lights, sun, only_switchoff=False):
    """Set lights brightness according to sun position."""
    illum = illumination(now, sun)
    if illum == 1:
        logger.info("It's the day!")
        poweroff_lights(bridge, lights)
        return
    # If we're here, it's the night
    if 0 < now.hour < 7:
        logger.info("It's the night, everybody asleep.")
        # From 1AM to 7AM, lights should better be off.
        poweroff_lights(bridge, lights)
        return
    # If we're here it's the night but someone may be up!
    if only_switchoff:
        return
    logger.info(
        f"It's not the day, illumination is at {illum:.0%}, switching on lights."
    )
    poweron_lights(bridge, lights, illum)


def transition_to_ct(bridge, lights, ct):
    for light in lights:
        bridge.set_light(light.light_id, "ct", ct, transitiontime=PERIOD * 60 * 10)


def redshift(bridge, now, lights, sun):
    coldest = 153  # in mireds.
    hottest = 500  # in mireds.

    illum = illumination(now, sun)
    if illum == 1:
        logger.info("It's daytime, transition to coldest temp.")
        transition_to_ct(bridge, lights, coldest)
        return
    if illum == 0:
        logger.info("It's nighttime, transition to hottest temp.")
        transition_to_ct(bridge, lights, hottest)
        return
    target = int(interpolate(illum, hottest, coldest))
    logger.info(
        f"[redshift] It's transition time ({illum:.0%} illuminated), set mireds={target} "
        "(132 is cold, 500 is hot)",
    )
    transition_to_ct(bridge, lights, target)


def check_if_cloudy(latitude, longitude):
    sky_conditions = run(
        ["weather", "--headers", "Sky conditions", "-q", f"{latitude},{longitude}"],
        stdout=PIPE,
        check=True,
        encoding="UTF-8",
    ).stdout.strip()
    logger.info("Sky is %s", sky_conditions)
    return any(bad in sky_conditions for bad in ("cloudy", "overcast"))


def main():
    args = parse_args()
    bridge = Bridge(args.hue_bridge)
    bridge.connect()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
    if args.list_sensors:
        list_sensors(bridge)
        sys.exit(0)
    if args.list_lights:
        list_lights(bridge)
        sys.exit(0)
    if sensor_pressed_not_long_ago(bridge, args.sensors):
        logger.info("Sensor pressed not long ago, leaving.")
        return
    city = lookup(args.city, database())
    is_cloudy = check_if_cloudy(city.latitude, city.longitude)
    if args.now:
        now = datetime.fromisoformat(args.now).astimezone().astimezone(timezone.utc)
    else:
        now = datetime.now(timezone.utc)
    sun = astral.sun.sun(city.observer, date=now.date())
    controlled_lights = [light for light in bridge.lights if light.name in args.lights]
    logger.info("Information for %s/%s", city.name, city.region)
    logger.info("Timezone: %s", city.timezone)

    def log_hour(date):
        return date.astimezone().strftime("%H:%M")

    logger.info(f"Now: {log_hour(now)}")
    logger.info(f"Dawn: {log_hour(sun['dawn'])}")
    logger.info(f"Sunrise: {log_hour(sun['sunrise'])}")
    logger.info(f"Sunset: {log_hour(sun['sunset'])}")
    logger.info(f"Dusk: {log_hour(sun['dusk'])}")
    if is_cloudy:
        logger.info("Sky being cloudy, power on 30m sooner, as if:")
        sun["sunset"] = sun["sunset"] - timedelta(minutes=30)
        sun["dusk"] = sun["dusk"] - timedelta(minutes=30)
        logger.info(f"Sunset: {log_hour(sun['sunset'])}")
        logger.info(f"Dusk: {log_hour(sun['dusk'])}")
    set_lights_brightness(
        bridge, now, controlled_lights, sun, only_switchoff=args.only_switchoff
    )
    redshift(bridge, now, controlled_lights, sun)


if __name__ == "__main__":
    main()
