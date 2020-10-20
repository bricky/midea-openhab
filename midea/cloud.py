import requests
import datetime
import json

from threading import Lock

from midea.security import security
import logging
import time

# The Midea cloud client is by far the more obscure part of this library, and without some serious reverse engineering
# this would not have been possible. Thanks Yitsushi for the ruby implementation. This is an adaptation to Python 3

VERSION = '0.1.7'


class cloud:
    SERVER_URL = "https://mapp.appsmb.com/v1/"
    CLIENT_TYPE = 1                 # Android
    FORMAT = 2                      # JSON
    LANGUAGE = 'en_US'
    APP_ID = 1017
    SRC = 17

    def __init__(self, app_key, email, password):
        # Get this from any of the Midea based apps, you can find one on Yitsushi's github page
        self.app_key = app_key
        self.login_account = email   # Your email address for your Midea account
        self.password = password

        # An obscure log in ID that is seperate to the email address
        self.login_id = None

        # A session dictionary that holds the login information of the current user
        self.session = {}

        # A list of home groups used by the API to seperate "zones"
        self.home_groups = []

        # A list of appliances associated with the account
        self.appliance_list = []

        self._api_lock = Lock()

        self.security = security(self.app_key)
        self._retries = 0

    def api_request(self, endpoint, args):
        """
        Sends an API request to the Midea cloud service and returns the results
        or raises ValueError if there is an error
        """
        self._api_lock.acquire()
        response = {}
        try:
            # Set up the initial data payload with the global variable set
            data = {
                'appId': self.APP_ID,
                'format': self.FORMAT,
                'clientType': self.CLIENT_TYPE,
                'language': self.LANGUAGE,
                'src': self.SRC,
                'stamp': datetime.datetime.now().strftime('%Y%m%d%H%M%S')
            }
            # Add the method parameters for the endpoint
            data.update(args)

            # Add the sessionId if there is a valid session
            if self.session:
                data['sessionId'] = self.session['sessionId']

            url = self.SERVER_URL + endpoint

            data['sign'] = self.security.sign(url, data)

            logging.debug('API call ' + endpoint + ': ' + repr(data))

            # POST the endpoint with the payload
            r = requests.post(url=url, data=data)

            response = json.loads(r.text)
        finally:
            self._api_lock.release()

        # Check for errors, raise if there are any
        if response['errorCode'] != '0':
            if endpoint != "user/login":    # hack to stop recursion problem on login failures
                self.handle_api_error(int(response['errorCode']), response['msg'])
            # If you don't throw, then retry
            logging.info("Retrying API call: '{}'".format(endpoint))
            self._retries += 1
            if self._retries < 3:
                return self.api_request(endpoint, args)
            else:
                raise RecursionError(response.get('msg'))

        self._retries = 0
        return response['result']

    def get_login_id(self):
        """
        Get the login ID from the email address
        """
        # let's assume that this doesn't change
        #if self.login_id: return self.login_id

        response = self.api_request("user/login/id/get", {
            'loginAccount': self.login_account
        })
        self.login_id = response['loginId']

    def login(self, force=False):
        """
        Performs a user login with the credentials supplied to the constructor
        """
        if not self.login_id or force:
            self.get_login_id()

        if not force and self.session:
            return  # Don't try logging in again, someone beat this thread to it

        logging.debug('Call to login with {} {} {}'.format(self.login_id, self.login_account, self.password))

        # Log in and store the session
        self.session = self.api_request("user/login", {
            'loginAccount': self.login_account,
            'password': self.security.encryptPassword(self.login_id, self.password)
        })

        self.security.accessToken = self.session['accessToken']
        if force: time.sleep(10)    # be patient for a forced login

    def list(self, home_group_id=-1):
        """
        Lists all appliances associated with the account
        """

        # If a homeGroupId is not specified, use the default one
        if home_group_id == -1:
            li = self.list_homegroups()
            home_group_id = next(
                x for x in li if x['isDefault'] == '1')['id']

        response = self.api_request('appliance/list/get', {
            'homegroupId': home_group_id
        })

        self.appliance_list = response['list']
        logging.debug("Device list: {}".format(self.appliance_list))
        return self.appliance_list

    def encode(self, data: bytearray):
        normalized = []
        for b in data:
            if b >= 128:
                b = b - 256
            normalized.append(str(b))

        string = ','.join(normalized)
        return bytearray(string.encode('ascii'))

    def decode(self, data: bytearray):
        data = [int(a) for a in data.decode('ascii').split(',')]
        for i in range(len(data)):
            if data[i] < 0:
                data[i] = data[i] + 256
        return bytearray(data)

    def appliance_transparent_send(self, id, data):
        if not self.session:
            self.login()

        logging.debug("Sending to {}: {}".format(id, data.hex()))
        encoded = self.encode(data)
        order = self.security.aes_encrypt(encoded)
        response = self.api_request('appliance/transparent/send', {
            'order': order.hex(),
            'funId': '0000',
            'applianceId': id
        })

        reply = self.decode(self.security.aes_decrypt(
            bytearray.fromhex(response['reply'])))

        logging.debug("Received from {}: {}".format(id, reply.hex()))
        return reply

    def list_homegroups(self, force_update=False):
        """
        Lists all home groups
        """

        # Get all home groups (I think the API supports multiple zones or something)
        if not self.home_groups or force_update:
            response = self.api_request('homegroup/list/get', {})
            self.home_groups = response['list']

        return self.home_groups

    def handle_api_error(self, error_code, message: str):

        def restart():
            logging.info("Restarting: '{}' - '{}'".format(error_code, message))
            self.session = None
            self.get_login_id()
            self.login()

        def force_restart():
            logging.info("Restarting forced: '{}' - '{}'".format(error_code, message))
            self.session = None
            self.get_login_id()
            self.login(True)

        def session_restart():
            logging.info("Restarting session: '{}' - '{}'".format(error_code, message))
            self.session = None
            self.login()

        def throw():
            if error_code == 3123: raise DeviceOfflineException()
            raise ValueError(error_code, message)

        def ignore():
            logging.info("Error ignored: '{}' - '{}'".format(error_code, message))

        error_handlers = {
            3176: ignore,          # The asyn reply does not exist.
            3106: force_restart,  # invalidSession.
            3144: restart,
            3004: session_restart,  # value is illegal.
            9999: session_restart,  # system error.
        }

        handler = error_handlers.get(error_code, throw)
        handler()


class DeviceOfflineException(Exception):
    pass