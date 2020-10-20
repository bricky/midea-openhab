# midea-openhab

Rough hack to connect a Midea (or compatible) aircon with Openhab.

Python 3.8, but probably works ok with anything later than Python 3.5

Requires `requests` and `sseclient`

```shell script
pip install requests
pip install sseclient
```

This is a horrendous ball of shite.  Don't use it if you value your sanity.

All credit to https://github.com/yitsushi/midea-air-condition for reverse engineering the protocol, and https://github.com/NeoAcheron/midea-ac-py for porting it to python.
