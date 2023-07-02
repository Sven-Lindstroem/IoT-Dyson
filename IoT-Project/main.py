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
change = False
# keeps the internal state of the Dyson
dyson_state = {
    "speed": 1,
    "is_on": False
}

# loads the state of the Dyson from the file
try:
    with open('dyson_state.py', 'r') as f:
        dyson_state = ujson.load(f)
# prints the state for debugging
        print("Dyson state is: ", dyson_state)
except:
# If the file does not exist the program will create it later on

     pass

global temp
max_time_intervall = int(config["maximum time interval"]) 

def main():
# test file existence
    test_file_presence()
 # set up MQTT
    set_up_mqtt()
    indicator_light()   
    global temp
    global change

    temp = getTemp()
    sendData(ujson.dumps({"temp":temp,
                          "speed":dyson_state["speed"],
                          "on_off":int(dyson_state["is_on"]),
                          "auto":int(autonomous_mode)}))

    last_data_sent = time.ticks_ms()
    while True:

        temp = getTemp()
# check msg from the command topic
        mqtt_client.check_msg()       

# If autonomous_mode is ON run autonomous
        if autonomous_mode == True:         
            autonomous()  
            t = 60                                      
 # else run manual
        else:                              
            manual()
            t = 3                         

 # If a change happened send the new state
        if change:                        
            sendData(ujson.dumps({"temp":temp,
                                  "speed":dyson_state["speed"],
                                  "on_off":int(dyson_state["is_on"]),
                                  "auto":int(autonomous_mode)}))

            last_data_sent = time.ticks_ms()
            change = False
# checks how long since the last temp has been sent
        elif (time.ticks_ms() - last_data_sent) > max_time_intervall:                 
            sendData(ujson.dumps({"temp":temp}))
            last_data_sent = time.ticks_ms()

        time.sleep(t)


# file presence
################################################################################################################
def test_file_presence():
# names of the files
    file_names = ['ir_signals/on_off.py','ir_signals/speed_down.py','ir_signals/speed_up.py']

# Loop through the file name
    for file in file_names:
        try:
# Try to open the file
            with open(file, 'r'):
# If the file is opened successfully move to the next file
                continue
        except:
            print("{} file not found".format(file))
# If the file is not opened call IR_receiver
            IR_reciver(file)
            time.sleep(1)
################################################################################################################

# IR Receiver
################################################################################################################
ir_rx_pin = Pin(16, Pin.IN)

def IR_reciver(file_name):
# ask the user to press the button corresponding to the file
    prompt = "Please point the remote at the IR receiver an press the {} button"

    if file_name == 'ir_signals/on_off.py':
        prompt = prompt.format("POWER")

    elif file_name == 'ir_signals/speed_down.py':
        prompt = prompt.format("DOWN")

    else:
        prompt = prompt.format("UP")

# prompt the user
    print(prompt)

# decode the IR signal
    lst = test(ir_rx_pin)

# creat the file and save the signal
    with open(file_name, 'w') as f:
        ujson.dump(lst, f)

################################################################################################################

# mqtt set up
################################################################################################################
# unique ID for the device
client_ID = ubinascii.hexlify(machine.unique_id())

PORT = 1883

# mosquitto ip address and credentials
mosquitto_server = config["MQTT broker IP"]
mosquitto_user = config["MQTT broker user"]
mosquitto_key = config["MQTT broker key"]                      

# The topic the dash bored publishes too
commands_topic = "devices/command"                                        

def set_up_mqtt():
    global mqtt_client
    print(f"Begin connection with MQTT Broker :: {mosquitto_server}")

# Connect to the MQTT broker  
    mqtt_client = MQTTClient(client_ID, mosquitto_server, PORT, mosquitto_user, mosquitto_key, keepalive=100)

 # set the callback function
    mqtt_client.set_callback(sub_cb)
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
    

# If autonomous_mode mode is ON only take action if the off signal is sent 
    if autonomous_mode == True:
        if msg == b'auto_on':
            return
        elif msg == b'auto_off': 
            autonomous_mode = False
            change = True
# sets the rotary sensor to the current speed when autonomous_mode is turned OFF
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

# On-Off indication light
################################################################################################################
LED_Green = Pin(12, Pin.OUT)
LED_Red = Pin(13, Pin.OUT)  

# The light indicated the on-off state of the Dyson to give a visual indication
def indicator_light():
    if dyson_state["is_on"] == True:
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
    if temp > dyson_on_temp and dyson_state["is_on"] == False:           
        dyson_On_Off()

    if dyson_state["is_on"] == True:    
      
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
# check button 
    button()
# If Dyson is on, check rotary 
    if dyson_state["is_on"]:
        rotary()  
    
################################################################################################################

# Button
################################################################################################################
push_button = Pin(27, Pin.IN, Pin.PULL_UP)
# check if the button is pressed
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
              initial_speed=dyson_state["is_on"]
              )

def rotary():
# get rotary value 
    speed_new = r.value()

# check if the value changed
    if dyson_state["is_on"] != speed_new:
        speed_change(speed_new)

def speed_change(speed_new):
# calculate the change in speed
    speed_change = speed_new - dyson_state["is_on"]

# chack if the change is positive or negative
    if speed_change > 0:    # positive the speed increases 
        direction = "is_on"
    else:                   # negative the speed decreases
        direction = "speed_down"

# update the internal state
    dyson_state["speed"] = speed_new
    dyson_speed(direction, speed_change)   


################################################################################################################

# IR Transmitter
################################################################################################################
pin = Pin(26)
ir = Player(pin)

def dyson_On_Off():
    global change

# open on_off.py file containing IR signal
    with open('ir_signals/on_off.py', 'r') as f:
        lst = ujson.load(f)
# sent signal
    ir.play(lst)
# wait 50ms so the transmitter has time to completely send the signal
    time.sleep_ms(50)

 # update internal state
    dyson_state['is_on'] = not dyson_state["is_on"]

    r.set(value = dyson_state["speed"])
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
    update_state()

################################################################################################################

# Update state
################################################################################################################
def update_state():
    global change
    change = True

 # dumps the Dyson state into the dyson_state file
    with open('dyson_state.py', 'w') as f:
        ujson.dump(dyson_state, f)        
# prints the current state for debugging                                
    print("Dyson state is: ", dyson_state)

################################################################################################################

# sent the data to the MQTT broker
################################################################################################################
data_topic = "devices/data"
def sendData(data_msg):
    print("data sent")
# sent current state including what triggered the sending
    mqtt_client.publish(topic=data_topic, msg=data_msg)
    
################################################################################################################

# Temperature sensor
################################################################################################################        
tempSensor = dht.DHT11(Pin(28))

def getTemp():
# get data from the DHT11  sensor
    tempSensor.measure()
    return tempSensor.temperature()

################################################################################################################

main()
