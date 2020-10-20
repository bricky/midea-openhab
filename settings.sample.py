'''
Copy this file to settings.py and put your real settings in there.
'''


APPKEY = 'app key goes here'
EMAIL = 'your login email'
PASSWORD = 'your login password'

# Tuple of aircons you want to sync
# If you have just one aircon, the syntax here is `('Aircon1',)` (i.e. including the trailing comma)
AIRCONS = ('Aircon1', 'Aircon2')

# Base url of your openhab.  Assumes that no auth is required.
OH_URL = 'http://openhab:8080'      # url of your openhab server

# How often do we poll the midea api for changes (in seconds)
# If you'll _only_ be changing the ac settings via openhab, then you can set this to something really
# really large (say 365*24*60*60).
MIDEA_POLL_FREQ_SECS = 900

