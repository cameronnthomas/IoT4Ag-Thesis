from machine import I2C
from machine import Pin, ADC
import ds1307
import utime
import machine
#import ustruct
import sys
import sdcard3
import uos

led = Pin(25, Pin.OUT)


#create adc object for battery reading
adc = ADC(Pin(26, mode=Pin.IN))

# Create I2C object for MPPT
i2c = machine.I2C(1, scl=machine.Pin(15), sda=machine.Pin(14), freq = 50000)

# HERE Create I2C object for RTC
i2c2 = machine.I2C(0, sda=machine.Pin(20), scl=machine.Pin(21))
utime.sleep_ms(100)
ds = ds1307.DS1307(i2c2)
utime.sleep_ms(500)

# Initialize time
f=utime.localtime()
g=f[0],f[1],f[2],f[6],(f[3]),f[4],f[5]
led.on()
utime.sleep_ms(500)
ds.halt(False)
utime.sleep_ms(500)
ds.datetime(g)
#variable = ds.datetime()
#print(variable)



i = 0

header = ['Date', 'Time','solar_v', 'solar_c', 'battery_v', 'battery_lc', 'battery_cc', 'PWM', 'status']
#header_str = ' '.join([str(item) for item in header_str])
header_str = " "
header_str = header_str.join(header)

    
# Assign chip select (CS) pin (and start it high)
cs = machine.Pin(9, machine.Pin.OUT)

# Intialize SPI peripheral (start with 1 MHz)
spi = machine.SPI(1,
                  baudrate=1000000,
                  polarity=0,
                  phase=0,
                  bits=8,
                  firstbit=machine.SPI.MSB,
                  sck=machine.Pin(10),
                  mosi=machine.Pin(11),
                  miso=machine.Pin(8))

# Initialize SD card
sd = sdcard3.SDCard(spi, cs)

# Mount filesystem
vfs = uos.VfsFat(sd)
uos.mount(vfs, "/sd")


###############################################################################
# Constants

# MPPT I2C address
MPPT_ADDR = 0x12

# Registers
REG_DEVID = 0x00
REG_STATUS = 0x02

# Other constants
DEVID = 0xE5


# write to I2C register within a specific period to enable watchdog function
# failure to write to control register causes the 5V power to be cycled for a specific period of seconds
# writing 0xEA to WDEN enables the watch dog function
# WDCNT contains watchdog timeout in seconds, 0 disables
# WDPWROFF contains the power off period in seconds, default is 10s


###############################################################################
# Functions

def isKthBitSet(n, k):
    if ((n >> (k - 1)) and 1):
        return True
    else:
        return False
        
def reg_write(i2c, addr, reg, data):
    """
    Write bytes to the specified register.
    """
    
    # Construct message
    msg = bytearray()
    msg.append(data)
    
    # Write out message to register
    i2c.writeto_mem(addr, reg, msg)
    
def reg_read(i2c, addr, reg, nbytes=1):
    """
    Read byte(s) from specified register. If nbytes > 1, read from consecutive
    registers.
    """
    
    # Check to make sure caller is asking for 1 or more bytes
    if nbytes < 1:
        return bytearray()
    
    # Request data from specified register(s) over I2C
    data = i2c.readfrom_mem(addr, reg, nbytes)
    
    return data


def mpptread():
    data = reg_read(i2c, MPPT_ADDR, 0, 2)
    #print(hex(int.from_bytes(data, "big")))
        
    # Wait before taking measurements
    utime.sleep(2.0)
    variable = ds.datetime()
    data = []
    #date = str(1)
    #time = str(2)
    date = str(variable[0]) + '/' + str(variable[1]) + '/' + str(variable[2])
    time = str(variable[4]) + ':' + str(variable[5])
    solar_v = reg_read(i2c, MPPT_ADDR, 0x06, 2)
    solar_v = str(int.from_bytes(solar_v, "big")/1000)
    solar_c = reg_read(i2c, MPPT_ADDR, 0x08, 2)
    solar_c = str(int.from_bytes(solar_c, "big")/1000)
    val = adc.read_u16()
    battery_v = ((val * (3.3 / 65535))* 4.9)
    battery_v = str(battery_v)
    battery_lc = reg_read(i2c, MPPT_ADDR, 0x12, 2)
    battery_lc = str(int.from_bytes(battery_lc, "big")/1000)
    battery_cc = reg_read(i2c, MPPT_ADDR, 0x14, 2)
    battery_cc = str(int.from_bytes(battery_cc, "big")/1000)
    pwm = reg_read(i2c, MPPT_ADDR, 0x04, 2)
    pwm = int.from_bytes(pwm,'big')
    pwm = (pwm >> 6) & 0x1FF
    pwm = str(pwm) 
    status = reg_read(i2c, MPPT_ADDR, REG_STATUS, 2)
    status_str = str(int.from_bytes(status, "big")/1000)
    STAT = (int.from_bytes(status, "big"))
    x = STAT & 0x7
    if (x == 0x0):
        state = ('Night - not charging')
    if (x == 0x1):
        state = ('Idle - not charging')
    if (x == 0x2):
        state = ('VSRCV - charger disabled for 3 seconds to let solar panel voltage float ')
    if (x == 0x3):
        state = ('Scan - determining solar panels current max power point')
    if (x == 0x4):
        state = ('BULK')
    if (x == 0x5):
        state = ('ABSORPTION')
    if (x == 0x6):
        state = ('FLOAT')
    #print(hex(x))
    
    data.extend((date, time, solar_v, solar_c, battery_v, battery_lc, battery_cc, pwm, state))
    data_str = " "
    data_str = data_str.join(data)


    utime.sleep(0.1)
    return data_str

###############################################################################
# Main

# Read device ID to make sure that we can communicate with the MPPT Solar Charger
# Should be 0x1012
            
i = 0
file = open("/sd/doesntmatter.txt", "a") # Opens file to write data to. If file doesnt exist, creates file; if file exists, append text
file.write(header_str + "\r\n") # Writes the header once at the beginning of the file
file.close()

while i < 1000:
    led.off()
    timedata = ds.datetime()
    if (timedata[4] > 6) and (timedata[5] % 1 == 0) and (timedata[6] < 10): # Ready to send data to the SD card every 30 minutes
        led.on()
        data_string = mpptread() # gets the solar panel data as a string
        file = open("/sd/doesntmatter.txt", "a")
        file.write(data_string + "\r\n") # Writes a new line then writes the data to that new line
        file.close() # closes the file after writing the data
        i += 1 # increment index
            
        
while(1):                
    led.on()
    #print('done')
           
#close("/sd/test_nebroof2.txt")      
# Open the file we just created and read from it
#with open("/sd/test_nebroof2.txt", "r") as file:
  # data = file.read()
  # print(data)


