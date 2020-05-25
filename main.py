#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Created on 25 Jan 2019

@author: dermot
'''
import json
import logging
import re
import threading
import time
from enum import Enum

import requests
import sseclient  # pip3 install sseclient

import settings
from msmart.device import air_conditioning_device as ac  # pip3 install msmart
from msmart.device import device as midea_device

# our default logging level
logging.basicConfig(format='%(asctime)s %(message)s', level=logging.DEBUG)

# silence urllib and requests
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

# Keyed on ac_name, values are air_conditioning_device
_devices = {}

# Keyed on ac_name, values are timestamps
_device_refresh_times = {}


# properties which only ever go from the midea -> oh
AC_RO_PROPERTIES = ('active', 'online', 'indoor_temperature', 'outdoor_temperature',)  # 'humidity')

# properties which can go in either direction
AC_RW_PROPERTIES = ('power_state', 'target_temperature', 'operational_mode', 'fan_speed',
                    'swing_mode', 'eco_mode', 'turbo_mode')


def devices_init():
    for ac_name, ac_info in settings.AIRCONS.items():
        client = midea_device(ac_info['ip'], int(ac_info['id']), ac_info['port'])
        _devices[ac_name] = client.setup()
        _device_refresh_times[ac_name] = 0


session = requests.Session()

_last_oh_values = {}
_last_midea_values = {}
_stop_event = None


def init_last_values():
    for ac_name in settings.AIRCONS.keys():
        if _last_oh_values.get(ac_name) is None:
            _last_oh_values[ac_name] = {k: 'NULL' for k in AC_RO_PROPERTIES + AC_RW_PROPERTIES}

        if _last_midea_values.get(ac_name) is None:
            _last_midea_values[ac_name] = {k: 'NULL' for k in AC_RO_PROPERTIES + AC_RW_PROPERTIES}


# def update_from_openhab(ac_name, ignore_nones=True):
#     """
#     Get the changes that have occurred in openhab since we last refreshed from there.
#
#     :param aircon:
#     :param ignore_nones:
#     :return dict    Returns a dict (may be empty) of properties that have changes along with their new values.
#         e.g. {
#             'power_state': 'ON',
#             'target_temperature: '24'
#         }
#
#         Note: values are always strings in oh, so they'll always be strings here.
#     """
#     changed_values = {}
#
#     # we only bother to pull in properties that could actually have changed on oh
#     for prop in AC_RW_PROPERTIES:
#         new_val = get_oh_value('ac_{}_{}'.format(ac_name, prop))
#         if new_val is None and ignore_nones: continue
#         if new_val != _last_oh_values[ac_name][prop]:
#             changed_values[prop] = new_val
#
#         _last_oh_values[ac_name][prop] = new_val
#
#     return changed_values


def clean_oh_value(raw_val):
    if raw_val == 'NULL':
        return None
    raw_val = re.sub('°C$', '', raw_val)
    raw_val = re.sub('Â$', '', raw_val)
    raw_val = re.sub('%$', '', raw_val)
    return raw_val.strip()


_blacklist_rest_items = set()


def get_oh_value(name):
    # Don't bother to query for blacklisted items (they're not there)
    if name in _blacklist_rest_items:
        return None

    url = settings.OH_URL + '/rest/items/' + name + '/state'
    response = session.get(url)
    if response.ok:
        return clean_oh_value(response.text)
    elif response.status_code == 404:
        logging.info('OH {} not found, blacklisting'.format(name))
        _blacklist_rest_items.add(name)

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

        enum_class = getattr(ac, name + '_enum')

        if isinstance(val, Enum):
            val_int = val.value
        elif isinstance(val, (float, int)):
            val_int = int(float(val))
        elif val.replace('.', '', 1).isdigit():
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
        if val.replace('.', '', 1).isdigit():
            return ac.operational_mode_enum(int(float(val)))
        return ac.operational_mode_enum[val.lower()]

    if name == 'fan_speed':
        if val.replace('.', '', 1).isdigit():
            return ac.fan_speed_enum(int(float(val)))
        return ac.fan_speed_enum[val.lower()]

    if name == 'swing_mode':
        if val.replace('.', '', 1).isdigit():
            return ac.swing_mode_enum(int(float(val)))
        return ac.swing_mode_enum[val.lower()]

    raise Exception('Cannot handle: {} with value {}'.format(name, val))


# def update_from_midea(device):
#     """
#     Get the changes that have occurred in midea since we last refreshed from there.
#     Note: this method does NOT refresh the device automatically.  Be sure to refresh manual before calling if needed.
#
#     :param device:    air_conditioning_device.  Midea device instance.
#     :return dict    Returns a dict (may be empty) of properties that have changes along with their new values.
#         e.g. {
#             'power_state': 'ON',
#             'target_temperature: '24'
#         }
#
#         Note: values are always forced to strings, for compatibility with oh.
#     """
#     changed_values = {}
#     aircon = device.name
#
#     # need to check all properties here
#     for prop in AC_RO_PROPERTIES + AC_RW_PROPERTIES:
#         new_val = force_to_string(prop, getattr(device, prop))
#         if new_val != _last_midea_values[aircon][prop]:
#             changed_values[prop] = new_val
#
#         _last_midea_values[aircon][prop] = new_val
#
#     return changed_values


def midea_to_openhab(ac_name):
    device = _devices[ac_name]

    try:
        logging.debug('Refreshing {}'.format(ac_name))
        device.refresh()
        _device_refresh_times[ac_name] = time.time()

        changed_values = {}

        # need to check all properties here
        for prop in AC_RO_PROPERTIES + AC_RW_PROPERTIES:
            new_val = force_to_string(prop, getattr(device, prop))
            if new_val != _last_midea_values[ac_name][prop]:
                changed_values[prop] = new_val

            _last_midea_values[ac_name][prop] = new_val

        # send each change to openhab
        for k, v in changed_values.items():
            set_oh_value('ac_{}_{}'.format(ac_name, k), v)
            _last_oh_values[ac_name][k] = force_to_string(k, v)
    except Exception:
        logging.exception('Device {} failed, skipping midea->openhab run'.format(ac_name))

#
# def openhab_to_midea():
#     global _devices
#     for ac_name, ac_info in settings.AIRCONS.items():
#         changes = update_from_openhab(ac_name)
#
#         if changes:
#
#             device = None
#             for d in _devices:
#                 if d.name == ac_name:
#                     device = d
#                     break
#
#             if device is None:
#                 raise Exception('Unable to locate device with name: ' + aircon)
#
#             try:
#                 # make sure that what we have is current
#                 device.refresh()
#
#                 for k, v in changes.items():
#                     logging.debug('Push to Midea {}: {} = {}'.format(aircon, k, v))
#                     setattr(device, k, force_to_midea(k, v))
#                     _last_midea_values[device.name][k] = force_to_string(k, v)
#
#                 device.apply()
#             except DeviceOfflineException:
#                 logging.warning(
#                     'Device {} is offline, not updating settings, and refreshing devices list'.format(device.name))
#                 _devices = _client_inst.devices()


def sse_init():
    global _stop_event

    # Looks like sseclient doesn't have a way of forcing a client disconnect, so the stop event here is a bit
    # pointless for now.  Leave it here anyway for the moment, I might be missing something obvious with client
    # disconnect (maybe we can do it via a requests Session?)
    _stop_event = threading.Event()
    sse_url = settings.OH_URL + '/rest/events'
    ac_set = set(['ac_' + ac_name for ac_name in settings.AIRCONS.keys()])

    def sse_loop():
        global _devices
        while not _stop_event.is_set():
            try:
                sse_client = sseclient.SSEClient(sse_url)
                for evt in sse_client:
                    data = json.loads(evt.data)
                    topic = data.get('topic')
                    topic_split = topic.split('/')
                    e_type = data.get('type')

                    if e_type == 'GroupItemStateChangedEvent':
                        item = topic_split[-3]
                    else:
                        item = topic_split[-2]

                    # logging.debug("{} {} {}".format(topic, e_type, item))

                    if not item.startswith('ac_'):
                        # all our items of interest start with ac_, so we can ignore anything that doesn't
                        continue

                    our_ac = None
                    ac_name = None
                    our_prop = None
                    for a in ac_set:
                        # Note: regexes would be a lot simpler here, but I think this is a lot more efficient
                        if item.startswith(a + '_'):
                            our_ac = a
                            ac_name = a[3:]
                            our_prop = item[len(a) + 1:]
                            break

                    if not our_ac:
                        continue  # doesn't match any ac we have

                    if our_prop not in AC_RW_PROPERTIES:
                        continue  # not a property that can be changed in oh

                    # only a subset of events interest us
                    if e_type in {'ItemStateChangedEvent', 'ItemStateEvent', 'GroupItemStateChangedEvent',
                                  'ItemCommandEvent'}:
                        payload = json.loads(data.get('payload', '{}'))
                        # print(repr(payload))
                        clean_val = clean_oh_value(payload.get('value'))
                        # print("Set {} on {} to {}".format(our_prop, our_ac, clean_val))
                        str_val = force_to_string(our_prop, clean_val)

                        device = _devices.get(ac_name)

                        if device is None:
                            raise Exception('Unable to locate device with name: ' + ac_name)

                        # only need to send to midea if something has changed
                        if _last_midea_values.get(ac_name, {}).get(our_prop) == str_val:
                            continue

                        try:
                            # make sure that what we have is current
                            # device.refresh() <- too slow, and probably not needed.

                            logging.debug('>>> Push to Midea {}: {} = {}'.format(ac_name, our_prop, clean_val))
                            setattr(device, our_prop, force_to_midea(our_prop, clean_val))
                            _last_midea_values[ac_name][our_prop] = str_val

                            device.apply()
                            _device_refresh_times[ac_name] = time.time()  # we've just pushed settings, effectively a refresh
                        except Exception:
                            logging.exception(
                                'Device {} failed, not updating settings'.format(device))

            except KeyboardInterrupt:
                # for this, we give up, regardless of the event state
                logging.info('Got keyboard interrupt, exiting sse loop.')
                return
            except Exception as e:
                print('Exception in sse_loop: ' + repr(e))
                logging.exception('Failure in sse_loop')
                # just sleep for a while and restart the loop.
                _stop_event.wait(5)

    threading.Thread(target=sse_loop, name="SSE Loop", daemon=True).start()


def main_loop():
    devices_init()
    init_last_values()
    for d in _devices.keys():
        midea_to_openhab(d)
    sse_init()
    try:
        while True:
            for d in _devices.keys():
                if time.time() - _device_refresh_times[d] > settings.MIDEA_POLL_FREQ_SECS:
                    midea_to_openhab(d)
            time.sleep(1)
    except KeyboardInterrupt:
        logging.warning('Shutting down in response to keyboard interrupt')
        _stop_event.set()
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
