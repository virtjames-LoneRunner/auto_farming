import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
import spidev
import time


from py_modules.error_handler import ErrorHandler

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
creds = credentials.Certificate('/home/raspberry/automated_farming/creds/automated_farming_creds.json')
databaseURL = "https://automated-farming-62ae9-default-rtdb.asia-southeast1.firebasedatabase.app"
app = firebase_admin.initialize_app(creds, {
                                    'databaseURL': databaseURL})

ref = db.reference('auto_farm/')
data_ref = ref.child('data')
controls_ref = ref.child('controls')

# Set initial values for controls_ref
# controls_ref.set({
#     'pump': HIGH,
#     'solenoid': LOW
# })
spi.open(BUS, DEVICE)
spi.max_speed_hz = 8000
spi.mode = 0

spi_2.open(BUS, DEVICE_2)
spi_2.max_speed_hz = 8000
spi_2.mode = 0



def main_loop():
    try:
        while True:
            # Retreive states
            try:
                control_states = controls_ref.get()
                pump_state = control_states["pump"]
                solenoid_state = control_states["solenoid"]

            # Handle errors
            except Exception as e:
                ErrorHandler(e)

            # Apply states
            try:
                # skip the first byte
                # only interested in getting data
                to_send = [240, 0x00, 0x00,
                           0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
                print("Tra: ARD_1: ", to_send)
                received_data = spi.xfer2(to_send)  # TODO Uncomment
                print("Res: ARD_1: ", received_data)

                to_send_2 = [240, int(pump_state), int(solenoid_state),
                           0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
                print("Tra: ARD_2: ", to_send_2)
                received_data_2 = spi_2.xfer2(to_send_2)

                print("Res: ARD_2: ", received_data_2)

            # Handle Errors
            except Exception as e:
                ErrorHandler(e)

            # Read sensors
            try:
                # received_data = [1, 2, 3, 4, 5, 6, 10, 20]  # TODO remove
                moisture_sensors_data = received_data[:6]

                water_level_data = received_data_2[0] + \
                    (received_data_2[1] * 0.01)

            # Handle errors
            except Exception as e:
                ErrorHandler(e)

            # Log data to DB
            try:
                data_ref.push({
                    'moisture_sensors_data': moisture_sensors_data,
                    'water_level_data': water_level_data
                })
                pass

            # Handle errors
            except Exception as e:
                ErrorHandler(e)

            # set some sleep time
            time.sleep(2)

    except KeyboardInterrupt:
        spi.close()
        spi_2.close()
        pass


if __name__ == "__main__":
#    setup()
    main_loop()
# main_loop()

