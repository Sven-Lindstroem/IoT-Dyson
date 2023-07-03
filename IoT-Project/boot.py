def do_connect():
    import network
    from time import sleep
    from config import wifi_secrets

    # put the modem on station mode
    wlan = network.WLAN(network.STA_IF)

    # checl if already connected
    if not wlan.isconnected():          
        print("connecting to network...")
        wlan.active(True)
        # Your WiFi credential
        wlan.connect(wifi_secrets["ssid"], wifi_secrets["password"])
        print("waiting for connection...", end='')

        # wait for connection
        while not wlan.isconnected() and wlan.status() >= 0:
            print('.',end='')
            sleep(1)
    # print the IP assigned by the router
    print('\nConnected on {}'.format(wlan.ifconfig()[0]))

try:
    do_connect()
except KeyboardInterrupt:
    print("Keyboard interrupt")
