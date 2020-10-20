# midea-openhab

Rough hack to connect a Midea (or compatible) aircon with Openhab.

Python 3.8, but probably works ok with anything later than Python 3.5.
This is the LAN version, which talks directly to the aircons.

MASSIVE thanks to [mac-zhou](https://github.com/mac-zhou/midea-msmart) for putting the lan part of this 
together.  This code is really just a wrapper for his.  Be a nice person, go and give him some money.

## Setup

```shell script
pip3 install requests
pip3 install sseclient
pip3 install msmart

midea-discover
```

Now jot down the `ip`, `port` and `id` of each a/c it finds, copy `settings.sample.py` to `settings.py`, and put your 
a/c details in there.

**Note:** If you're switching from the `master` branch, note that the `AIRCONS` in `settings.py` is now a dict with
ip's and such.  You'll need to update it.

```shell script
python3 main.py
```

On the openhab side, you'll need to set up some of the following items for it to talk to:

```
Switch ac_Aircon1_active
Switch ac_Aircon1_online
Number ac_Aircon1_indoor_temperature
Number ac_Aircon1_outdoor_temperature
Switch ac_Aircon1_power_state
Number ac_Aircon1_target_temperature
Number ac_Aircon1_operational_mode
Number ac_Aircon1_fan_speed
Number ac_Aircon1_swing_mode
Switch ac_Aircon1_eco_mode
Switch ac_Aircon1_turbo_mode
```

The above being for an a/c called `Aircon1`.  Anything that you're not interested in syncing (e.g. many devices don't 
measure outside_temperature), you can simply omit. The script will not attempt to sync them if they're not present.

At startup the script will give you a list of items it expects anyway.

We use EventSource to get the changes from openhab (so they should be reflected more-or-less immediately), but we
must poll the a/c for changes, so these will take up to `MIDEA_POLL_FREQ_SECS` to be communicated back to openhab.

This repo is a horrendous ball of shite.  Don't use it.  Go staple your ear to something, it's more fun.

## Thanks

https://github.com/mac-zhou/midea-msmart for the LAN protocol, https://github.com/yitsushi/midea-air-condition 
for reverse engineering the protocol originally, and https://github.com/NeoAcheron/midea-ac-py for porting it to python.
