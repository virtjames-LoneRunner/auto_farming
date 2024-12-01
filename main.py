import spidev
import time
from py_modules.error_handler import ErrorHandler
from datetime import datetime

import pyrebase
time.sleep(3) #give enough time to initialize
BUS = 0
DEVICE = 0
DEVICE_2 = 1

HIGH = True
LOW = False
moisture_sensors_data = [0, 0, 0, 0, 0, 0]
water_level_data = 0

spi = spidev.SpiDev()
spi_2 = spidev.SpiDev()

# Setup connection to Firebase
# Firebase configuration
config = {
  "apiKey": "AIzaSyBAwk34N0XewjFLAI7B8P8I6kBOYUOA2Gk",
  "authDomain": "automated-farming-62ae9.firebaseapp.com",
  "databaseURL": "https://automated-farming-62ae9-default-rtdb.asia-southeast1.firebasedatabase.app",
  "projectId": "automated-farming-62ae9",
  "storageBucket": "automated-farming-62ae9.appspot.com",
  "messagingSenderId": "352159346483",
  "appId": "1:352159346483:web:0f421f72c93fb157bd9846",
  "measurementId": "G-NPLEMQDWY7"
}

firebase_app = pyrebase.initialize_app(config)
db = firebase_app.database()

#db.child("auto_farm").child("data").set([])

spi.open(BUS, DEVICE)
spi.max_speed_hz = 4000
spi.mode = 0

spi_2.open(BUS, DEVICE_2)
spi_2.max_speed_hz = 4000
spi_2.mode = 0

sensor_data_cleaned = [0,0,0,0,0,0]

def map_value(x, in_min, in_max, out_min, out_max):
    return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min

def main_loop():
    print("Started")
    last_sent_hour = None
    try:
        while True:
            # Retreive states
            now = datetime.now()

            try:
                control_states = db.child("auto_farm").child("controls").get().val()
                pump_state = control_states["pump"]
                solenoid_state = control_states["solenoid"]
                moisture_calibration = control_states["moisture_calibration"]

            # Handle errors
            except Exception as e:
                print("Retrieving error")
                ErrorHandler(e)

            # Apply states
            try:
                # skip the first byte
                # only interested in getting data
                to_send = [240, 0x00, 0x00,
                           0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0, 0, 0, 0]
                #print("Tra: ARD_1: ", to_send)
                rd = spi.xfer2(to_send)  # TODO Uncomment

                sensor_data_cleaned[0] = (rd[1] << 8) | rd[2]
                sensor_data_cleaned[1] = (rd[3] << 8) | rd[4]
                sensor_data_cleaned[2] = (rd[5] << 8) | rd[6]
                sensor_data_cleaned[3] = (rd[7] << 8) | rd[8]
                sensor_data_cleaned[4] = (rd[9] << 8) | rd[10]
                sensor_data_cleaned[5] = (rd[11] << 8) | rd[12]
                print("Sensor: ", sensor_data_cleaned)
                #print("received: ", rd)

                to_send_2 = [240, int(pump_state), int(solenoid_state),
                           0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
                #print("Tra: ARD_2: ", to_send_2)
                received_data_2 = spi_2.xfer2(to_send_2)

                #print("Res: ARD_2: ", received_data_2)

            # Handle Errors
            except Exception as e:
                ErrorHandler(e)

            # Read sensors
            try:
                moisture_sensors_data = sensor_data_cleaned 
                calibrated_moisture_data = [0, 0, 0, 0, 0, 0]
                for i, data in enumerate(moisture_sensors_data):
                   moisture_temp = map_value(data, 
                                             moisture_calibration[i]["wet"],
                                             moisture_calibration[i]["dry"],
                                             100,
                                             0)
                   if moisture_temp < 0:
                       moisture_temp = 0
                   elif moisture_temp > 100:
                       moisture_temp = 100
                
                   calibrated_moisture_data[i] = moisture_temp

                water_level_data = (received_data_2[1] + \
                    (received_data_2[2] * 0.01))-10 #minus 10 for error correction
                water_level_data = round(water_level_data, 2)

                average_moisture = 0
                total_moisture = 0

                for data in calibrated_moisture_data:
                    total_moisture = total_moisture + data;

                average_moisture = total_moisture / 6


                act_set = control_states[control_states["active_phase"]]
                if not control_states["manual_control"]:
                    # moisture_level
                    #if average_moisture < act_set["moisture_level"]["min"] or water_level_data < act_set["water_level"]["min"]:
                    #print("Average Moisture: ", average_moisture, "Set Min Moisture: ", act_set["moisture_level"]["min"])
                    if average_moisture > 0 and average_moisture < act_set["moisture_level"]["min"]:
                        pump = True
                        valve = False
                    if water_level_data > act_set["water_level"]["max"]:
                        pump = False
                        valve = True
                    else:
                        pump = False
                        valve = False

                    control_states["pump"] = pump
                    control_states["solenoid"] = valve
                    control_states["average_moisture"] = average_moisture

                    db.child("auto_farm").child("controls").set(control_states)

                print("Calibrated Moisture Data: ", calibrated_moisture_data)
                print("Water Level: ", water_level_data)
                print("Average Moisture: ", average_moisture)

            # Handle errors
            except Exception as e:
                ErrorHandler(e)

            # Log data to DB
            try:
                if not (now.minute % 20 == 0 and now.minute != last_sent_hour):
                    print("Did not send")
                    time.sleep(15)
                    continue

                db.child("auto_farm").child("data").push({
                    'datetime': now.strftime("%Y-%m-%d %H:%M:%S"),
                    'moisture_sensors_data': moisture_sensors_data,
                    'calibrated_moisture_data': calibrated_moisture_data,
                    'water_level_data': water_level_data
                })
                print("Sent Data to Firebase at ", now)
                last_sent_hour = now.minute # Make Note of the last hour we sent data

            # Handle errors
            except Exception as e:
                ErrorHandler(e)

            # set some sleep time
            time.sleep(10)

    except KeyboardInterrupt:
        spi.close()
        spi_2.close()
        pass

time.sleep(3)
main_loop()
# main_loop()

