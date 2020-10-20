# midea-openhab

Rough hack to connect a Midea (or compatible) aircon with Openhab.

## Master Branch (via Midea cloud)
This is the master branch, which currently communicates with the a/c via midea cloud.  Also check the 
[LAN branch](https://github.com/bricky/midea-openhab/tree/lan), which communicates directly with the device.

Developed for Python 3.8, but probably works ok with anything later than Python 3.5

Requires `requests` and `sseclient`

```shell script
pip install requests
pip install sseclient
```

### Notes & Known issues:
- Some devices reset to 17&deg;C on occasion, when we refresh data from midea cloud.  I believe this is because these devices update
their current (inside & outside) temperatures independent of the other settings, and the code doesn't currently 
understand these "special" updates (and as I don't have a device that does this, it's difficult to fix).  If you're
having this issue, you can set `MIDEA_POLL_FREQ_SECS` to something very big (say `60*60*24*365`), so it will effectively
only poll the midea api once (at startup).  Thereafter the 17&deg;C resets should (hopefully) go away.  Alternatively, 
use the [LAN branch](https://github.com/bricky/midea-openhab/tree/lan), which doesn't have this issue.
- Midea cloud is very unreliable, and will regularly drop your connection.  The code will try to automatically reconnect
when it does, but you might want to wrap it in a loop anyway, e.g. 
```shell script
while true; do python3 main.py; sleep 10; done
```
- There's a (fairly low) limit on the number of logins you can make (in the order of 20/hour) which you'll possibly hit if you
restart this a lot.  If you hit it, just wait an hour and try again.
- This is a horrendous ball of shite.  Don't use it.

# Thanks

All credit to https://github.com/yitsushi/midea-air-condition for reverse engineering the protocol, and https://github.com/NeoAcheron/midea-ac-py for porting it to python.
