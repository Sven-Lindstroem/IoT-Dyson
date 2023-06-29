def do_connect():
    import network
    from time import sleep
    from config import wifi_secrets
    import machine


    wlan = network.WLAN(network.STA_IF)     # put modem on station mode

    if not wlan.isconnected():              # checl if already connected          
        print("connecting to network...")
        wlan.active(True)                   # activate network interface
        # set power mode to get WIFI power-saving off (if needed)
        wlan.config(pm = 0xa11140)
        wlan.connect(wifi_secrets["ssid"], wifi_secrets["password"]) # Your WiFi credential
        
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


