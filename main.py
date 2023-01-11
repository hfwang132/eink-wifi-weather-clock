import time
import network
import socket
import struct
from machine import I2C, SoftSPI, Pin
from ssd1680 import SSD1680 # e-ink display
from bmp280 import BMX280 # temperature and pressure
from ahtx0 import AHT20 # temperature and humidity
from mq135 import MQ135 # air quality (ppm)

# init

bmp_aht_i2c = I2C(1, scl=Pin(15), sda=Pin(14), freq=200000)

bmp = BMX280(bmp_aht_i2c, addr=0x77)

aht = AHT20(bmp_aht_i2c, address=0x38)

mq135 = MQ135(0)

eink_busy = Pin(18, Pin.IN)
eink_cs = Pin(19, Pin.OUT)
eink_dc = Pin(20, Pin.OUT)
eink_res = Pin(21, Pin.OUT)

spi_ssd1680 = SoftSPI(
            baudrate=400000,
            polarity=0,
            phase=0,
            sck=Pin(16),
            mosi=Pin(17),
            miso=Pin(2)
            )

ssd1680 = SSD1680(
        spi_ssd1680,
        eink_dc,
        eink_busy,
        eink_cs,
        eink_res,
        )

ssd1680.init()

# wifi

NTP_DELTA = 2208988800 - 8 * 3600
host = "pool.ntp.org"

led = Pin("LED", Pin.OUT)
led.off()

ssid = 'WP'
password = '13729974087A'

def set_time():
    NTP_QUERY = bytearray(48)
    NTP_QUERY[0] = 0x1B
    addr = socket.getaddrinfo(host, 123)[0][-1]
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.settimeout(1)
        res = s.sendto(NTP_QUERY, addr)
        msg = s.recv(48)
    finally:
        s.close()
    val = struct.unpack("!I", msg[40:44])[0]
    t = val - NTP_DELTA    
    tm = time.gmtime(t)
    machine.RTC().datetime((tm[0], tm[1], tm[2], tm[6] + 1, tm[3], tm[4], tm[5], 0))

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(ssid, password)

max_wait = 10
while max_wait > 0:
    if wlan.status() < 0 or wlan.status() >= 3:
        break
    max_wait -= 1
    print('waiting for connection...')
    time.sleep(1)

if wlan.status() != 3:
    led.off()
    raise RuntimeError('network connection failed')
else:
    print('connected')
    status = wlan.ifconfig()
    print( 'ip = ' + status[0] )
    led.on()


# time init

set_time()
localtime = time.localtime()
localtime_last = localtime

# loop function

def loop():
    global localtime, localtime_last
    set_time()
    localtime = time.localtime()
    
    if (localtime[4] != localtime_last[4]):
        # temperture, pressure, humidity
        temperature = (bmp.temperature + aht.temperature) / 2
        pressure = bmp.pressure / 1000
        humidity = aht.relative_humidity
        
        # air quality
        rzero = mq135.get_rzero()
        corrected_rzero = mq135.get_corrected_rzero(temperature, humidity)
        resistance = mq135.get_resistance()
        ppm = mq135.get_ppm()
        corrected_ppm = mq135.get_corrected_ppm(temperature, humidity)

        print("MQ135 RZero: " + str(rzero) +"\t Corrected RZero: "+ str(corrected_rzero)+
              "\t Resistance: "+ str(resistance) +"\t PPM: "+str(ppm)+
              "\t Corrected PPM: "+str(corrected_ppm)+"ppm")
        
        # display
        ssd1680.clear()
        
        base_y = 8
        inc_y = 25
        base_x = 10
        
        ssd1680.show_string("%d/%d/%d %02d:%02d" % (localtime[0], localtime[1], localtime[2], localtime[3],
                                                  localtime[4]), base_x, base_y, multiplier=2)
        ssd1680.show_string("Godfly"                                , 210   , base_y            , multiplier=2)
        ssd1680.show_string("Temperature: %.1f   C"  % temperature  , base_x, base_y + inc_y    , multiplier=2)
        ssd1680.show_string("Pressure   : %.2f kPa"  % pressure     , base_x, base_y + 2 * inc_y, multiplier=2)
        ssd1680.show_string("Humidity   : %.1f   %%" % humidity     , base_x, base_y + 3 * inc_y, multiplier=2)
        ssd1680.show_string("PPM        : %.1f   "   % corrected_ppm, base_x, base_y + 4 * inc_y, multiplier=2)
        
        ssd1680.update()
        
        localtime_last = localtime

# loop

while True:
    try:
        print(localtime)
        loop()
        
    except OSError as e:
        print("an error occurred")
        print(e)
    
    except Exception as e:
        print("an error occurred")
        led.off()
        raise e
    
    time.sleep(0.5)
    led.toggle()
    
    
