from rotary_irq_rp2 import RotaryIRQ
from ir_rx.acquire import test
from mqtt import MQTTClient
from ir_tx import Player
from machine import Pin
from config import config
import ubinascii
import machine
import ujson
import time
import dht


autonomous_mode = False 

# keeps the internal state of the dyson
dyson_state = {
    "speed" : 1,
    "is_on": False
}

# loads the state of the dyson from the file
try:
    with open('dyson_state.py', 'r') as f:
        dyson_state = ujson.load(f)
        print("Dyson state is: ", dyson_state)  # prints the state for debugging
except:
     pass                                       # if the file dose not exist the program will creat it later on

global temp
change = False
max_time_intervall = int(config["maximum time intervall"]) 

def main():
    test_file_presence()                    # test file existence
    set_up_mqtt()                           # set up MQTT
    indicator_light()   
    global temp
    global change
    temp = getTemp()

    sentData(ujson.dumps({"temp":temp,"speed":dyson_state["speed"],"on_off":int(dyson_state['is_on']),"auto":int(autonomous_mode)}))
    last_data_sent = time.ticks_ms()

    while True: 
        temp = getTemp()
        mqtt_client.check_msg()       # check msg from the command topic

        if autonomous_mode == True:         # if autonomous_mode mode is on run autonomous
            autonomous()  
            t = 60                                      

        else:                               # if temp mode is off run manual
            manual()
            t = 3                                        

        if change:                         # if a change happened sent the new state
            sentData(ujson.dumps({"temp":temp,"speed":dyson_state["speed"],"on_off":int(dyson_state['is_on']),"auto":int(autonomous_mode)}))
            last_data_sent = time.ticks_ms()
            change = False
        elif (time.ticks_ms() - last_data_sent) > max_time_intervall:                  # check how long since the last temp has been sent
            data_msg = ujson.dumps({"temp":temp})
            sentData(data_msg)
            last_data_sent = time.ticks_ms()

        time.sleep(t)


# file presence
################################################################################################################
def test_file_presence():
    file_names = ['ir_signals/on_off.py','ir_signals/speed_down.py','ir_signals/speed_up.py'] # names of the files
    for file in file_names:         # loop through the file name
        try:
            with open(file, 'r'):   # try to open file
                continue            # if file is opened successfully move to the next file
        except:
            print("{} file not found".format(file))
            IR_reciver(file)        # if file is not opened call IR receiver

################################################################################################################

# IR reciver
################################################################################################################
ir_rx_pin = Pin(16, Pin.IN)

def IR_reciver(file_name):
    # ask the user to press the button corresponding to the file
    prompt = "Please point the romote at the IR reciver an press the {} button"

    if file_name == 'ir_signals/on_off.py':
        prompt = prompt.format("POWER")

    elif file_name == 'ir_signals/speed_down.py':
        prompt = prompt.format("DOWN")

    else:
        prompt = prompt.format("UP")
        
    print(prompt)                       # prompt the user

    lst = test(ir_rx_pin)               # decode the IR signal
    with open(file_name, 'w') as f:     # creat the file and save the signal
        ujson.dump(lst, f)

################################################################################################################

# mqtt set up
################################################################################################################
client_ID = ubinascii.hexlify(machine.unique_id())  # unique ID for the device

PORT = 1883

# mosquitto ip address and credentials
mosquitto_server = config["MQTT broker IP"]
mosquitto_user = "admin"
mosquitto_key = "arthur"                       

# the topic the dash bored publishes too
commands_topic = "devices/command"                                        

def set_up_mqtt():
    global mqtt_client
    print(f"Begin connection with MQTT Broker :: {mosquitto_server}")

    # connect to the mqtt broker  
    mqtt_client = MQTTClient(client_ID, mosquitto_server, PORT, mosquitto_user, mosquitto_key, keepalive=100) 
    mqtt_client.set_callback(sub_cb)                                                            # set the call back function
    mqtt_client.connect()

    # subscribe to the command topic
    mqtt_client.subscribe(commands_topic)

    print(f"connected to MQTT Broker :: {mosquitto_server}")

################################################################################################################

# sub routine
################################################################################################################
def sub_cb(topic, msg):
    print(msg)
    global change
    global autonomous_mode
    

    # if autonomous_mode mode is ON only take action if the off signal is sent 
    if autonomous_mode == True:
        if msg == b'auto_on':
            return
        elif msg == b'auto_off': 
            autonomous_mode = False
            change = True
            # sets rotary sensor to current speed when autonomous_mode is turned OFF
            r.set(value = dyson_state["speed"]) 
    else:
        if msg == b"power":                    
            dyson_On_Off()
        elif msg == b"auto_on":                
            autonomous_mode = True
            change = True
        elif msg == b"auto_off":
            return
        elif dyson_state["is_on"] == True:      
            r.set(value=int(msg))

################################################################################################################

# On Off indication light
################################################################################################################
LED_Green = Pin(12, Pin.OUT)
LED_Red = Pin(13, Pin.OUT)  

# the light indicated the on off state of the dyson to give visual indication
def indicator_light():
    if dyson_state['is_on'] == True:
        LED_Red.value(0)
        LED_Green.value(1)
    else:
        LED_Red.value(1)
        LED_Green.value(0)

################################################################################################################

# This code is run when the autonomous mode is ON
################################################################################################################
dyson_on_temp = config["dyson on temp"]
dyson_off_temp = config["dyson off temp"]

medium_break_point = config["medium break point"]
fast_break_point = config["fast break point"]   

def autonomous():

    # checks breakpoint and takes action accordingly 
    if temp > dyson_on_temp and dyson_state['is_on'] == False:           
        dyson_On_Off()

    if dyson_state['is_on'] == True:    
      
        if temp < dyson_off_temp:           
            dyson_On_Off()
                
        elif temp < medium_break_point:
            if dyson_state["speed"] != 3:
                speed_change(3)

        elif temp < fast_break_point: 
            if dyson_state["speed"] != 6:
                speed_change(6)

        elif dyson_state["speed"] != 9:   
                speed_change(9)
                
               
################################################################################################################

# This code is run when the autonomous mode is OFF
################################################################################################################
def manual(): 
    button()                    # check button
    rotary()                    # check rotary   
    
################################################################################################################

# Button
################################################################################################################
push_button = Pin(27, Pin.IN, Pin.PULL_UP)
# check if button is pressed
def button(): 
    if push_button.value() == False:           
        dyson_On_Off()

################################################################################################################

# Rotation sensor set up
################################################################################################################
r = RotaryIRQ(pin_num_clk=21,
              pin_num_dt=22,
              min_val=1,
              max_val=10,
              reverse=False,
              range_mode=RotaryIRQ.RANGE_BOUNDED,
              half_step=True,
              invert=True,
              initial_speed=dyson_state['speed']
              )

def rotary():
    speed_new = r.value()                   # get rotary value 
    if dyson_state['speed'] != speed_new:   # check if value changed
        speed_change(speed_new)

def speed_change(speed_new):
    speed_change = speed_new - dyson_state['speed'] # calculate change in speed
    # chack if change is positive or negative
    if speed_change > 0:    # positive the speed increases 
        direction = 'speed_up'
    else:                   # negative the speed decreases
        direction = 'speed_down'

    dyson_state['speed'] = speed_new        # update the internal state
    dyson_speed(direction, speed_change)   


################################################################################################################

# IR transmiter
################################################################################################################
pin = Pin(26)
ir = Player(pin)

def dyson_On_Off():
    global change
    # open on_off.py file containing IR signal
    with open('ir_signals/on_off.py', 'r') as f:
        lst = ujson.load(f)

    ir.play(lst)        # sent signal
    time.sleep_ms(50)   # wait 50ms so tranmitter has time to completly sent the signal

    dyson_state['is_on'] = not dyson_state['is_on']                      # update internal state

    change = True
    update_state()      
    indicator_light()   

def dyson_speed(direction, speed_change):
    global change
    # open file containing up or down IR signal
    direction ='ir_signals/{}.py'.format(direction) 
    with open(direction, 'r') as f:
        lst = ujson.load(f)                         
    # sent signal once for every unit of speed change
    for x in range(abs(speed_change)):             
        ir.play(lst)
        time.sleep_ms(500)
    change = True
    update_state()

################################################################################################################

# Update state
################################################################################################################
def update_state():
    with open('dyson_state.py', 'w') as f:
        ujson.dump(dyson_state, f)           # dumps the dyson state into the dyson_state file                              
    print("Dyson state is: ", dyson_state)   # prints the current state for debuggin

################################################################################################################

# sent the data to MQTT broker
################################################################################################################
data_topic = "devices/data"
def sentData(data_msg):
    print("data sent")
    # sent current state including what tiggered the sending
    mqtt_client.publish(topic=data_topic, msg=data_msg)
    
################################################################################################################

# Temperature sensor
################################################################################################################        
tempSensor = dht.DHT11(machine.Pin(28))

def getTemp():
    # get data from DHT11  sensor
    tempSensor.measure()
    return tempSensor.temperature()

################################################################################################################

main()