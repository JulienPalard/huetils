# Huetils

This is just a set of script I'm using to manage lights in my home.

Bet it can be usefull for someone else.


## hue-room-control

This is the manager for a room, it can be used for a living room and for a bedroom.

It switchs the lights on and off according to the sun, and does some
redshifting, to select the lights use `--lights`. To help you naming
the lights use `--list-lights`.

It stop doing anything for a few time when a human touch a button
(humans gets control), to watch for sensors, use the `--sensors`
flag. To help you finding sensor names, use `--list-sensors`.

I use it like in a crontab (every 10 minutes) like this, for a living room:

    hue-room-control Paris --hue-bridge 10.0.0.7 --sensors 'Salon 1' 'Salon 2' 'Salon 3' --lights 'Salon 1' 'Salon 2' 'Salon 3'

And for a bedroom (only caring abount switching the light off at night):

    hue-room-control Paris --hue-bridge 10.0.0.7 --sensors 'Left bed dimmer' 'Right bed dimmer' --lights 'Bed lightstrip' 'Room light' --only-switchoff


## hue-thermometer

This is an outside temperature thermometer based on the `weather-util`
(Debian) package, use it to control a single light, like the entrance one.

Color scheme is:

     40°C -> purple
     30°C -> red
     20°C -> orange
     10°C -> yellow
      0°C -> green
    -10°C -> blue

Use it as an hourly cron as:

    hue-thermometer --hue-bridge 10.0.0.7 --light Entrée --city Paris --weather LFPV
