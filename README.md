# midea-openhab

Rough hack to connect a Midea (or compatible) aircon with Openhab.

Python 3.8, but probably works ok with anything later than Python 3.5.
This is the LAN version, which talks directly to the aircons.

MASSIVE thanks to mac-zhou for putting the lan part of this together:

https://github.com/mac-zhou/midea-msmart

```shell script
pip3 install requests
pip3 install sseclient
pip3 install msmart

midea-discover
```

Now jot down the `ip`, `port` and `id` of each a/c it finds, copy `settings.sample.py` to `settings.py`, and put your 
a/c details in there.

On the openhab side, you'll need to set up the following items for it to talk to:

```
ac_Aircon1_active
ac_Aircon1_online
ac_Aircon1_indoor_temperature
ac_Aircon1_outdoor_temperature
ac_Aircon1_outdoor_temperature
ac_Aircon1_power_state
ac_Aircon1_target_temperature
ac_Aircon1_operational_mode
ac_Aircon1_fan_speed
ac_Aircon1_swing_mode
ac_Aircon1_eco_mode
ac_Aircon1_turbo_mode
```

The above being for an a/c called `Aircon1`.  Anything that you're not interested in syncing (e.g. many devices don't 
measure outside_temperature), you can simply omit. The script will not attempt to sync them if they're not present.

The code here is a horrendous ball of shite.  Don't use it if you value your sanity.

Credit to https://github.com/yitsushi/midea-air-condition for reverse engineering the protocol, and https://github.com/NeoAcheron/midea-ac-py for porting it to python.
