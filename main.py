'''
Created on 25 Jan 2019

@author: dermot
'''

from enum import Enum
import logging
import re
import time

import requests

from midea.client import client as midea_client
from midea.device import air_conditioning_device
import settings
from midea.cloud import DeviceOfflineException

# our default logging level
logging.basicConfig(format='%(asctime)s %(message)s', level=logging.DEBUG)

# silence urllib and requests
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

client_inst = None
devices = None


def midea_init():
    global client_inst, devices
    client_inst = midea_client(settings.APPKEY, settings.EMAIL, settings.PASSWORD)
    devices = client_inst.devices()


# properties which only ever go from the midea -> oh
AC_RO_PROPERTIES = ('active', 'online', 'indoor_temperature', 'outdoor_temperature', )#'humidity')

# properties which can go in either direction
AC_RW_PROPERTIES = ('power_state', 'target_temperature', 'operational_mode', 'fan_speed',
                    'swing_mode', 'eco_mode', 'turbo_mode')


session = requests.Session()


_last_oh_values = {}
_last_midea_values = {}


def init_last_values():
    for aircon in settings.AIRCONS:
        if _last_oh_values.get(aircon) is None:
            _last_oh_values[aircon] = {k: 'NULL' for k in AC_RO_PROPERTIES + AC_RW_PROPERTIES}

        if _last_midea_values.get(aircon) is None:
            _last_midea_values[aircon] = {k: 'NULL' for k in AC_RO_PROPERTIES + AC_RW_PROPERTIES}


def update_from_openhab(aircon, ignoreNones=True):
    '''
    Get the changes that have occurred in openhab since we last refreshed from there.

    :param aircon:
    :return dict    Returns a dict (may be empty) of properties that have changes along with their new values.
        e.g. {
            'power_state': 'ON',
            'target_temperature: '24'
        }

        Note: values are always strings in oh, so they'll always be strings here.
    '''
    changed_values = {}

    # we only bother to pull in properties that could actually have changed on oh
    for prop in AC_RW_PROPERTIES:
        new_val = get_oh_value('ac_{}_{}'.format(aircon, prop))
        if new_val is None and ignoreNones: continue
        if new_val != _last_oh_values[aircon][prop]:
            changed_values[prop] = new_val

        _last_oh_values[aircon][prop] = new_val

    return changed_values

_blacklist_rest_items = set()

def get_oh_value(name):
    # Don't bother to query for blacklisted items (they're not there)
    if name in _blacklist_rest_items:
        return None

    url = settings.OH_URL + '/rest/items/' + name + '/state'
    response = session.get(url)
    if response.ok:
        if response.text == 'NULL': return None
        result = re.sub('°C$', '', response.text)
        result = re.sub('Â$', '', result)
        result = re.sub('%$', '', result)
        return result.strip()
    elif response.status_code == 404:
        logging.info('OH {} not found, blacklisting'.format(name))
        _blacklist_rest_items.add(name)
    else:
        return None

def set_oh_value(name, value):
    # Don't bother to update blacklisted items (they're not there)
    if name in _blacklist_rest_items:
        return None

    # need to pull the property name from the rest name
    matches = re.search(r"ac_[a-zA-Z\d]+_([\w]+)", name)
    if matches:
        prop_name = matches.group(1)
    else:
        prop_name = name

    # oh values are always strings.  Make this one if it isn't already
    value = force_to_string(prop_name, value)

    logging.debug('Setting OH: {} ({}) = {}'.format(name, prop_name, value))

    url = settings.OH_URL + '/rest/items/' + name + '/state'
    response = session.put(url, data=value)
    if response.ok:
        return True
    elif response.status_code == 404:
        logging.info('OH {} not found, blacklisting'.format(name))
        _blacklist_rest_items.add(name)

    return False


# # properties which only ever go from the midea -> oh
# AC_RO_PROPERTIES = ('active', 'online', 'indoor_temperature', 'outdoor_temperature')
#
# # properties which can go in either direction
# AC_RW_PROPERTIES = ('power_state', 'target_temperature', 'operational_mode', 'fan_speed',
#                     'swing_mode', 'eco_mode', 'turbo_mode')

def force_to_string(name, val):
    if val is None or val == 'NULL':
        return 'NULL'

    # these are booleans - either 'ON' or 'OFF'
    if name in {'active', 'online', 'power_state', 'eco_mode', 'turbo_mode'}:
        if val in {1, 1.0, 'on', 'ON', '1', '1.0', True, 'y', 'Y'}:
            return 'ON'
        else:
            return 'OFF'

    # these are floating point strings, always include a decimal
    if name in {'indoor_temperature', 'outdoor_temperature', 'target_temperature', 'humidity'}:
        return str(float(val))

    # these are enums.  We store them as their numeric value
    if name in {'operational_mode', 'fan_speed', 'swing_mode'}:

        enum_class = getattr(air_conditioning_device, name + '_enum')

        if isinstance(val, Enum):
            val_int = val.value
        elif isinstance(val, (float, int)):
            val_int = int(float(val))
        elif val.replace('.','',1).isdigit():
            # if it's a numeric string we just need to convert it to an int
            val_int = int(float(val))
        elif isinstance(val, str):
            # any non-numeric string, just assume it's a string version of the enum
            val_int = enum_class[val.lower()].value
        else:
            raise Exception('Unable to handle value "{}" for property "{}"'.format(val, name))

        return str(float(enum_class(val_int).value))

def force_to_midea(name, val):
    # booleans
    if name in {'power_state', 'eco_mode', 'turbo_mode'}:
        if val is None: return False
        return val == 'ON'

    # ints
    if name in {'target_temperature'}:
        return int(float(val))

    if name == 'operational_mode':
        if val.replace('.','',1).isdigit():
            return air_conditioning_device.operational_mode_enum(int(float(val)))
        return air_conditioning_device.operational_mode_enum[val.lower()]

    if name == 'fan_speed':
        if val.replace('.','',1).isdigit():
            return air_conditioning_device.fan_speed_enum(int(float(val)))
        return air_conditioning_device.fan_speed_enum[val.lower()]

    if name == 'swing_mode':
        if val.replace('.','',1).isdigit():
            return air_conditioning_device.swing_mode_enum(int(float(val)))
        return air_conditioning_device.swing_mode_enum[val.lower()]

    raise Exception('Cannot handle: {} with value {}'.format(name, val))



def update_from_midea(device):
    '''
    Get the changes that have occurred in midea since we last refreshed from there.
    Note: this method does NOT refresh the device automatically.  Be sure to refresh manual before calling if needed.

    :param device:    air_conditioning_device.  Midea device instance.
    :return dict    Returns a dict (may be empty) of properties that have changes along with their new values.
        e.g. {
            'power_state': 'ON',
            'target_temperature: '24'
        }

        Note: values are always forced to strings, for compatibility with oh.
    '''
    changed_values = {}
    aircon = device.name

    # need to check all properties here
    for prop in AC_RO_PROPERTIES + AC_RW_PROPERTIES:
        new_val = force_to_string(prop, getattr(device, prop))
        if new_val != _last_midea_values[aircon][prop]:
            changed_values[prop] = new_val

        _last_midea_values[aircon][prop] = new_val

    return changed_values


# def refresh_midea():
#     devs = midea_client.devices()
#     #print(repr(devs))
#
#     for device in devs:
#         if not isinstance(device, air_conditioning_device):
#             print('Skipping device, not an a/c: {}, {} {} {} {}'.format(device.name, device.model_number, device.serial_number, device.type))
#             continue
#
#         device.refresh()
#         print('''
#     id: {0.id},
#     name: {0.name},
#     model_number: {0.model_number},
#     serial_number: {0.serial_number},
#     type: {0.type},
#     active: {0.active},
#     online: {0.online},
#     audible_feedback: {0.audible_feedback},
#     target_temperature: {0.target_temperature},
#     indoor_temperature: {0.indoor_temperature},
#     outdoor_temperature: {0.outdoor_temperature},
#     operational_mode: {0.operational_mode},
#     fan_speed: {0.fan_speed},
#     swing_mode: {0.swing_mode},
#     eco_mode: {0.eco_mode},
#     turbo_mode: {0.turbo_mode},
#     power_state: {0.power_state}
# '''.format(device))


def midea_to_openhab():
    global devices
    for device in devices:
        if not isinstance(device, air_conditioning_device):
            logging.info('Skipping device, not an a/c: {}, {} {} {} {}'.format(device.name, device.model_number, device.serial_number, device.type))
            continue

        if not device.name in settings.AIRCONS:
            logging.info('Skipping device {}, not one of ours'.format(device.name))
            continue

        try:
            logging.debug('Refreshing {}'.format(device.name))
            device.refresh()

            changes = update_from_midea(device)

            # send each change to openhab
            for k,v in changes.items():
                set_oh_value('ac_{}_{}'.format(device.name, k), v)
                _last_oh_values[device.name][k] = force_to_string(k, v)
        except DeviceOfflineException:
            logging.warning('Device {} is offline, skipping midea->openhab run, and refreshing devices list'.format(device.name))
            devices = client_inst.devices()



def openhab_to_midea():
    global devices
    for aircon in settings.AIRCONS:
        changes = update_from_openhab(aircon)

        if changes:

            device = None
            for d in devices:
                if d.name == aircon:
                    device = d
                    break

            if device is None:
                raise Exception('Unable to locate device with name: ' + aircon)

            try:
                # make sure that what we have is current
                device.refresh()

                for k,v in changes.items():
                    logging.debug('Push to Midea {}: {} = {}'.format(aircon, k, v))
                    setattr(device, k, force_to_midea(k, v))
                    _last_midea_values[device.name][k] = force_to_string(k, v)


                device.apply()
            except DeviceOfflineException:
                logging.warning('Device {} is offline, not updating settings, and refreshing devices list'.format(device.name))
                devices = client_inst.devices()



def main_loop():
    midea_init()
    init_last_values()
    last_oh_refresh = 0
    last_midea_refresh = 0
    try:
        while True:
            if time.time() - last_midea_refresh > settings.MIDEA_POLL_FREQ_SECS:
                midea_to_openhab()
                last_midea_refresh = time.time()

            if time.time() - last_oh_refresh > settings.OPENHAB_POLL_FREQ_SECS:
                openhab_to_midea()
                last_oh_refresh = time.time()

            time.sleep(1)
    except KeyboardInterrupt:
        logging.warning('Shutting down in response to keyboard interrupt')
        return True
    except Exception as e:
        print('Exception: ' + repr(e))
        logging.exception('Failure in main loop')
        return False

if __name__ == '__main__':

    should_quit = False
    restart_count = 0
    while not should_quit and restart_count < 100:
        should_quit = main_loop()
        restart_count += 1
        if not should_quit:
            time.sleep(10.0)
