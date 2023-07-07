from rotary_irq_rp2 import RotaryIRQ
from ir_rx.acquire import test
from mqtt import MQTTClient
from ir_tx import Player
from machine import Pin
import ubinascii
import machine
import ujson
import time
import dht
from config import config

state_changed = False

# Load the state of the Dyson from the file
current_state = {
    "speed": 1,
    "is_on": False,
    "auto_on": False
}

try:
    with open('dyson_state.py', 'r') as f:
        current_state = ujson.load(f)
        # prints the state for debugging
        print("Dyson state is: ", current_state)
except:
    print("Failed to load Dyson state file. Using default state.")

# Create instances of temperature sensor, pins, and LED indicators
temperature_sensor = dht.DHT11(Pin(28))
push_button = Pin(27, Pin.IN, Pin.PULL_UP)
LED_green = Pin(12, Pin.OUT)
LED_red = Pin(13, Pin.OUT) 
ir = Player(Pin(26))

def main():
    check_ir_signal_files()
    set_up_mqtt()
    indicator_light()   
    global state_changed
    temp = get_temp()
    send_data(ujson.dumps({
        "temp":temp,
        "speed":current_state["speed"],
        "on_off":int(current_state["is_on"]),
        "auto":int(current_state["auto_on"])
    }))
    max_time_intervall = int(config["maximum time interval"]) 
    last_data_sent = time.ticks_ms()

    while True:
        temp = get_temp()
        mqtt_client.check_msg()       
        if current_state["auto_on"]:         
            autonomous(temp)  
            sleep_time = 60                                      
        else:                              
            manual()
            sleep_time = 3                            
        if state_changed:                        
            send_data(ujson.dumps({
                "temp":temp,
                "speed":current_state["speed"],
                "on_off":int(current_state["is_on"]),
                "auto":int(current_state["auto_on"])
            }))
            last_data_sent = time.ticks_ms()
            state_changed = False
            update_state()
        # checks how long since the last temp has been sent
        elif (time.ticks_ms() - last_data_sent) > max_time_intervall:                 
            send_data(ujson.dumps({"temp":temp}))
            last_data_sent = time.ticks_ms()
        time.sleep(sleep_time)

# Check if the required IR signal files are present
def check_ir_signal_files():
    file_names = ['on_off.py','speed_down.py','speed_up.py']
    for file in file_names:
        try:
            with open("ir_signals/{}".format(file), 'r'):
                continue
        except:
            print("{} file not found".format(file))
            acquire_ir_signal(file)
            time.sleep(1)

# Acquire IR signals from the remote control
def acquire_ir_signal(file_name):
    prompt = {
        'on_off.py': "POWER",
        'speed_down.py': "DOWN",
        'speed_up.py': "UP"
    }
    # prompt the user press the button corresponding to the file
    print("Please point the remote at the IR receiver an press the {} button".format(prompt[file_name]))
    lst = test(Pin(16, Pin.IN))
    # creat the file and save the signal
    with open("ir_signals/{}".format(file_name), 'w') as f:
        ujson.dump(lst, f)

# Set up MQTT client
PORT = 1883
client_ID = ubinascii.hexlify(machine.unique_id())
mosquitto_server = config["MQTT broker IP"]
mosquitto_user = config["MQTT broker user"]
mosquitto_key = config["MQTT broker key"]

data_topic = "devices/data"
commands_topic = "devices/command"

mqtt_client = MQTTClient(client_ID, mosquitto_server, PORT, mosquitto_user, mosquitto_key, keepalive=120)

def set_up_mqtt():
    print(f"Begin connection with MQTT Broker :: {mosquitto_server}")
    try:
        mqtt_client.set_callback(sub_cb)
        mqtt_client.connect()
        mqtt_client.subscribe(commands_topic)
        print(f"connected to MQTT Broker :: {mosquitto_server}")
    except Exception as e:
        print(f"Failed to connect to MQTT Broker :: {mosquitto_server}")
        print(f"Error: {e}")

# Callback function for MQTT messages
def sub_cb(topic, msg):
    print("Received message:", msg)
    global state_changed
    # If autonomous_mode mode is ON only take action if the off signal is sent 
    if msg == b'auto_power':
        print("autonomous mode is now off")
        current_state["auto_on"] =  not current_state["auto_on"]
        state_changed = True
        # Set the rotary sensor to the current speed    
        rotation.set(value = current_state["speed"])

    if not current_state["auto_on"]:
        if msg == b"power":                    
            ON_OFF()
        elif current_state["is_on"]:      
            rotation.set(value=int(msg))

# On-Off indication light
def indicator_light():
    LED_green.value(int(current_state["is_on"]))
    LED_red.value(int(not current_state["is_on"]))

# Autonomous mode
dyson_on_temp = int(config["dyson on temp"])
dyson_off_temp = int(config["dyson off temp"])
medium_break_point = int(config["medium break point"])
fast_break_point = int(config["fast break point"])

def autonomous(temp):
    # checks breakpoint and takes action accordingly 
    if not current_state["is_on"] and temp > dyson_on_temp:           
        ON_OFF()

    if current_state["is_on"]:    
        if temp < dyson_off_temp:           
            ON_OFF() 
        elif temp < medium_break_point:
            if current_state["speed"] != 3:
                change_speed_to(3)
        elif temp < fast_break_point: 
            if current_state["speed"] != 6:
                change_speed_to(6)
        elif current_state["speed"] != 9:   
                change_speed_to(9)      

# Manual mode
def manual():
    if push_button.value() == False:           
        ON_OFF()
    if current_state["is_on"]:
        rotary()  

# Rotation sensor setup
rotation = RotaryIRQ(pin_num_clk=21,
              pin_num_dt=22,
              min_val=1,
              max_val=10,
              reverse=False,
              range_mode=RotaryIRQ.RANGE_BOUNDED,
              half_step=True,
              invert=True,
              initial_speed=current_state["speed"]
              )

def rotary():
    speed_new = rotation.value()
    if current_state["speed"] != speed_new and speed_new >= 1 and speed_new <= 10:
        change_speed_to(speed_new)

def change_speed_to(speed_new):
    # Calculate the direction and magnitude of speed change
    speed_difference = speed_new - current_state["speed"]

    # Determine the direction based on the speed difference
    if speed_difference > 0:
        direction = "speed_up"  # Increase speed
    else:
        direction = "speed_down"  # Decrease speed

    current_state["speed"] = speed_new
    speed_change(direction, abs(speed_difference))

# Send the corresponding IR signals for the given speed difference
def speed_change(direction, speed_difference):
    global state_changed
    state_changed = True
    file_path ='ir_signals/{}.py'.format(direction)
    try:
        with open(file_path, 'r') as f:
            lst = ujson.load(f)
                     
        # Send the signal for each unit of speed change
        for x in range(speed_difference):             
            ir.play(lst)
            time.sleep_ms(500)
    except OSError:
        print("Error: Failed to open IR signal file.")

# Send the ON/OFF IR signal to control the Dyson
def ON_OFF():
    global state_changed
    state_changed = True
    try:
        with open('ir_signals/on_off.py', 'r') as f:
            lst = ujson.load(f)
        ir.play(lst)
        # Wait for the transmitter to finish sending the signal
        time.sleep_ms(50)

        current_state['is_on'] = not current_state["is_on"]
        rotation.set(value=current_state["speed"])

        indicator_light()   
    except OSError:
        print("Error: Failed to open IR signal file.")

# Update the state file with the current Dyson state
def update_state():
    try:
        with open('dyson_state.py', 'w') as f:
            ujson.dump(current_state, f)        
        # prints the current state for debugging                                
        print("Dyson state is: ", current_state)
    except Exception as e:
        print("Error updating state:", e)

# Send data to the MQTT broker
def send_data(data_msg):
    print("data sent")
    mqtt_client.publish(topic=data_topic, msg=data_msg) 

# Get temperature from the sensor
def get_temp():
    temperature_sensor.measure()
    return temperature_sensor.temperature()

main()
