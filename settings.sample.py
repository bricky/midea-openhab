"""
Copy this file to settings.py and put your real settings in there.
"""

# Login stuff not needed for lan control
# APPKEY = 'app key goes here'
# EMAIL = 'your login email'
# PASSWORD = 'your login password'

# Dict of aircons you want to sync.  Keys here (the aircon names) are just for openhab (the devices themselves
# don't appear to know their names).  Keep it ascii, and avoid using underscores.
# You'll probably need to run `midea-discover` to get the device ids.
AIRCONS = {
    'Aircon1': {
        'ip': '192.168.100.101',
        'port': 6444,
        'id': 12345678901234
    },
    'Aircon2': {
        'ip': '192.168.100.102',
        'port': 6444,
        'id': 23456789012345
    }
}

# Base url of your openhab.  Assumes that no auth is required.
OH_URL = 'http://openhab:8080'      # url of your openhab server

# How often do we poll the midea device for changes (in seconds).
# Don't set this too short, each aircon can take a few seconds to respond.  Anything upwards
# of 30 seconds should be ok.
MIDEA_POLL_FREQ_SECS = 60
