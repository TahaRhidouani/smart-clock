import time
from datetime import datetime
import json
import requests
import colorsys
from rgbmatrix import RGBMatrix, RGBMatrixOptions
from rgbmatrix import graphics

# Key variables
apikey = "352bcac06997a1c7ea0224d8acaee9d7" # From openweathermap
deviceID = "b113eb05-7cbe-475f-870d-8ce0d8971e3e" # Device ID for smartthings
city = "Ottawa, CA" # Weather location
weatherRefresh = 120 # Weather refresh (in seconds)
timezone = -4 # Hours from UTC

# #Configuration of the display
options = RGBMatrixOptions()
options.rows = 32
options.cols = 64
options.chain_length = 1
options.parallel = 1
options.row_address_type = 0
options.multiplexing = 0
options.pwm_bits = 11
options.brightness = 60
options.pwm_lsb_nanoseconds = 130
options.led_rgb_sequence = "RBG"
options.gpio_slowdown = 4
options.pixel_mapper_config = ""
matrix = RGBMatrix(options = options)

canvas = matrix.CreateFrameCanvas()
canvas.Clear()

# Graphics stuff
font_1 = graphics.Font()
font_1.LoadFont("/home/pi/rpi-rgb-led-matrix/bindings/python/samples/time.bdf")
font_2 = graphics.Font()
font_2.LoadFont("/home/pi/rpi-rgb-led-matrix/bindings/python/samples/text.bdf")

# Initializing variables
delay = weatherRefresh
temperature, description, sunset, sunrise = "", "", "" ,""
brightness = 1
dateIntensity = 0
weatherIntensity = 0
showDate = True
firstTime = True
differenceColorAmount = [0, 0, 0]

# Starting date and weather color
dateColor = graphics.Color(0, 0, 0)
weatherColor = graphics.Color(0, 0, 0)

# Function to draw all the elements on the matrix
def display():
    canvas.Clear()

    if (showDate):
        graphics.DrawText(canvas, font_2, getSmallTextOffset(date), 28, dateColor, date)
    else:
        graphics.DrawText(canvas, font_2, getSmallTextOffset(weather_text), 28, weatherColor, weather_text)
    graphics.DrawText(canvas, font_1, getBigTextOffset(clock) + 1, 21, graphics.Color(current_color[0], current_color[1], current_color[2]), clock)

    matrix.SwapOnVSync(canvas)

# To center the clock text
def getBigTextOffset(big_text):
    big_text_length = 0
    for i in range(len(big_text)):
        if (list(big_text)[i] == ":"):
            big_text_length += 6
        elif (list(big_text)[i] == "1"):
            big_text_length += 9
        else:
            big_text_length += 12
    return (64 - big_text_length)/2

# To center the date and weather text
def getSmallTextOffset(small_text):
    small_text_length = 0
    for i in range(len(small_text)):
        if (list(small_text)[i] == " "):
            small_text_length += 1
        elif (list(small_text)[i] == u"\N{DEGREE SIGN}" or list(small_text)[i].lower() == "i"):
            small_text_length += 2
        elif (list(small_text)[i] == ","):
            small_text_length += 3
        else:
            small_text_length += 4
    return (64 - small_text_length)/2 + 1

while True:    
    if (round(delay,2) % 1 == 0):
        try:
            lights = requests.get("https://api.smartthings.com/v1/devices/" + deviceID + "/status", headers = {'Authorization': 'Bearer 6acbcf0a-e58b-45b9-9605-9be747206419'}).json()
        except:
            noWifi = True
        else:
            noWifi = False

    # Weather
    if (delay == weatherRefresh and noWifi == False):
        weather = requests.get("http://api.openweathermap.org/data/2.5/weather?appid="+ apikey + "&q=" + city + "&units=metric").json()
        if weather["cod"] != "404":
            temperature = str(int(weather["main"]["feels_like"])) + u"\N{DEGREE SIGN}"
            description = weather["weather"][0]["description"].capitalize()
            sunset = datetime.fromtimestamp(weather["sys"]["sunset"]).strftime('%H')
            sunrise = datetime.fromtimestamp(weather["sys"]["sunrise"]).strftime('%H')
            darkOutside = ((int(sunset) + 1) < datetime.now().strftime("%H") < (int(sunrise) + 24)) # Check if it's dark outside
            weather_text = temperature + "   " + description.split()[-1]
            delay = 0.00

    # Set colors to lights color
    status = lights["components"]["main"]["switch"]["switch"]["value"]
    target_color = colorsys.hsv_to_rgb(float((lights["components"]["main"]["colorControl"]["hue"]["value"])) / 100, float(lights["components"]["main"]["colorControl"]["saturation"]["value"]) / 100, round(brightness))        

    # If it's not dark outside and lights are off, make the text white
    if ((status == "off" or noWifi) and darkOutside == False):
        target_color = colorsys.hsv_to_rgb(0, 0, round(brightness/1.2, 2))

    # Default value for first loop (to prevent crash to unset variable)
    if (firstTime and noWifi == False):
        current_color = [target_color[0]*255, target_color[1]*255, target_color[2]*255]
        temp_color = colorsys.hsv_to_rgb(float((lights["components"]["main"]["colorControl"]["hue"]["value"])) / 100, float(lights["components"]["main"]["colorControl"]["saturation"]["value"]) / 100, round(brightness))
        firstTime = False
    
    # If color changed, calculate difference
    if (temp_color != target_color):
        temp_color = target_color
        for i in range(3):
            differenceColorAmount[i] = abs(round(target_color[i]*255) - round(current_color[i]))

    if (current_color != [target_color[0]*255, target_color[1]*255, target_color[2]*255]):
        
        # Increase the color by 1/30 of its final value every refresh
        for i in range(3):
            if (round(target_color[i]*255) < round(current_color[i])):
                current_color[i] -= (differenceColorAmount[i]/30)
            elif (round(target_color[i]*255) > round(current_color[i])):
                current_color[i] += (differenceColorAmount[i]/30)

        # Checks if the values are valid
        for i in range(3):
            if (current_color[i] > 255):
                current_color[i] = 255
            elif (current_color[i] < 0):
                current_color[0] = 0
            else:
                current_color[0] = round(current_color[0])

    # Switch between date and weather
    if (int(str(delay).split('.')[0][-1]) < 5):
        showDate = True
        if (int(str(delay).split('.')[0][-1]) == 4 and int(str(delay).split('.')[1]) >= 45):
            dateIntensity -= 3.5
        elif (int(str(delay).split('.')[0][-1]) == 0 and int(str(delay).split('.')[1]) < 45):
            dateIntensity += 3.5
        dateColor = graphics.Color(dateIntensity * brightness, dateIntensity * brightness, dateIntensity * brightness)
    else:
        showDate = False
        if (int(str(delay).split('.')[0][-1]) == 9 and int(str(delay).split('.')[1]) >= 45):
            weatherIntensity -= 3.5
        elif (int(str(delay).split('.')[0][-1]) == 5 and int(str(delay).split('.')[1]) < 45):
            weatherIntensity += 3.5
        weatherColor = graphics.Color(weatherIntensity * brightness, weatherIntensity * brightness, weatherIntensity * brightness)

    # Time
    clock = datetime.now().strftime("%I:%M")
    ampm = datetime.now().strftime("%p")

    # Date
    date = datetime.today().strftime("%a, %b %d")

    if (darkOutside):
        if (status == "off" or noWifi):
            # Turn off display
            if (round(brightness, 2) != 0):
                brightness -= 0.02
                display()
            else:
                canvas.Clear()
        else:
            # Turn on display
            if (round(brightness, 2) != 1):
                brightness += 0.02
            display()
    else:
        # Turn on display
        if (round(brightness, 2) != 1):
            brightness += 0.02
        display()
    
    time.sleep(0.01)
    delay += 0.01
