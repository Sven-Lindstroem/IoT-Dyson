def do_connect():
    import network
    from time import sleep
    from config import wifi_secrets

# put the modem on station mode
    wlan = network.WLAN(network.STA_IF)

 # checl if already connected
    if not wlan.isconnected():          
        print("connecting to network...")

# activate network interface
        wlan.active(True)
        wlan.config(pm="PM_POWERSAVE")

# Your WiFi credential
        wlan.connect(wifi_secrets["ssid"], wifi_secrets["password"])

        print("waiting for connection...", end='')

# checl if it is connected otherwise wait
        while not wlan.isconnected() and wlan.status() >= 0:
            print('.',end='')
            sleep(1)

# pritn the IP assigned by router
    ip = wlan.ifconfig()[0]
    print('\nConnected on {}'.format(ip))
    return ip

try:
    ip = do_connect()
except KeyboardInterrupt:
    print("Keyboard interrupt")
