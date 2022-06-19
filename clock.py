import time
from datetime import datetime
import json
import sys
import requests
import colorsys
import subprocess
from rgbmatrix import RGBMatrix, RGBMatrixOptions
from rgbmatrix import graphics

# API variables
with open('/home/pi/clock/apikeys', 'r') as file:
    for line in file:
        key = line.strip().split(":")
        if (key[0] == 'apikey'):
            apikey = key[1] # From openweathermap
        elif (key[0] == 'auth'):
            auth = key[1] # Authorization key for smartthings

# Key variables
city = "Ottawa, CA" # Weather location
weatherRefresh = 120 # Weather refresh (in seconds)
timezone = -4 # Hours from UTC
animationIdle = 3 # Number of seconds before moving to next text (for subtext)
animationSpeed = 0.05 # Higher number = Faster animation (but choppier)
dimBrightness = 0.02

# Configuration of the display
options = RGBMatrixOptions()
options.rows = 32
options.cols = 64
options.chain_length = 1
options.parallel = 1
options.row_address_type = 0
options.multiplexing = 0
options.pwm_bits = 11
options.brightness = 100
options.pwm_lsb_nanoseconds = 50
options.limit_refresh_rate_hz = 500
options.pixel_mapper_config = "Rotate:180" # If display is upside down
# options.pixel_mapper_config = "" # If display is right way up
options.led_rgb_sequence = "RBG"
options.hardware_mapping = 'adafruit-hat-pwm'
options.gpio_slowdown = 4
options.drop_privileges = False
options.disable_hardware_pulsing = False
matrix = RGBMatrix(options = options)

canvas = matrix.CreateFrameCanvas()
canvas.Clear()

# Graphics stuff
font_1 = graphics.Font()
font_1.LoadFont("/home/pi/clock/time.bdf")
font_2 = graphics.Font()
font_2.LoadFont("/home/pi/clock/text.bdf")

# Initializing variables
firstTime = True
delay = weatherRefresh
temperature, description, sunset, sunrise = "", "", "" ,""
brightness = 1
differenceColorAmount = [0, 0, 0]
subtexts = [datetime.today().strftime("%a, %b %d"), ""]
subtextIndex = 0 # Which element of the array is the subtext showing
subOpacity = 0 # Starting opacity of the subtext
animationTime = 0 # Gets incremented as the animation progresses
fading = True # Is there a current animation running?
fadingIn = True # Is the subtext animation fading in or fading out?

# Starting date and weather color
clockColor = graphics.Color(0, 0, 0)
subTextColor = graphics.Color(0, 0, 0)

# Function to draw all the elements on the matrix
def display():
    canvas.Clear()

    graphics.DrawText(canvas, font_1, getBigTextOffset(clock) + 1, 20, clockColor, clock)
    graphics.DrawText(canvas, font_2, getSmallTextOffset(subtexts[subtextIndex]), 28, subTextColor, subtexts[subtextIndex])
    
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
    try:
        devicesList = requests.get("https://api.smartthings.com/v1/devices/", headers = {'Authorization': 'Bearer ' + auth}).json()
        deviceID = devicesList['items'][0]['deviceId'] # Getting device ID for the light
        break
    except Exception as e:
        canvas.Clear()

        clockColor = graphics.Color(200, 200, 200)
        subTextColor = graphics.Color(255, 0, 0)

        graphics.DrawText(canvas, font_1, getBigTextOffset(datetime.now().strftime("%I:%M")) + 1, 20, clockColor, datetime.now().strftime("%I:%M"))
        graphics.DrawText(canvas, font_2, getSmallTextOffset("No  internet"), 28, subTextColor, "No  internet")
        
        matrix.SwapOnVSync(canvas)
        time.sleep(3)


while True:
    try:
        if (round(delay,2) % 1 == 0): # Check lights every second
            lights = requests.get("https://api.smartthings.com/v1/devices/" + deviceID + "/status", headers = {'Authorization': 'Bearer '+ auth}).json()

        # Weather
        if (round(delay, 2) == weatherRefresh):
            weather = requests.get("http://api.openweathermap.org/data/2.5/weather?appid="+ apikey + "&q=" + city + "&units=metric").json()
            if weather["cod"] != "404":
                temperature = str(int(weather["main"]["feels_like"])) + u"\N{DEGREE SIGN}"
                description = weather["weather"][0]["description"].capitalize()
                sunset = datetime.fromtimestamp(weather["sys"]["sunset"]).strftime('%H')
                sunrise = datetime.fromtimestamp(weather["sys"]["sunrise"]).strftime('%H')
                darkOutside = ((int(sunset)) < int(datetime.now().strftime("%H")) or int(datetime.now().strftime("%H")) <= (int(sunrise))) # Check if it's dark outside
                subtexts[1] = temperature + "   " + (description.split()[-1] if description != "Clear sky" else description.split()[0])
                delay = 0.00

        # Set colors to lights color
        status = lights["components"]["main"]["switch"]["switch"]["value"]
        target_color = colorsys.hsv_to_rgb(float((lights["components"]["main"]["colorControl"]["hue"]["value"])) / 100, float(lights["components"]["main"]["colorControl"]["saturation"]["value"]) / 100, round(brightness))        

        # If it's not dark outside and lights are off, make the text white
        if (status == "off"):
            target_color = (1, 1, 0.94)

        # Default value for first loop (to prevent crash to unset variable)
        if (firstTime):
            current_color = [round(target_color[0]*255), round(target_color[1]*255), round(target_color[2]*255)]
            temp_color = colorsys.hsv_to_rgb(float((lights["components"]["main"]["colorControl"]["hue"]["value"])) / 100, float(lights["components"]["main"]["colorControl"]["saturation"]["value"]) / 100, round(brightness))
            firstTime = False
        
        # If color changed, calculate difference
        if (temp_color != target_color):
            temp_color = target_color
            for i in range(3):
                differenceColorAmount[i] = abs(round(target_color[i]*255) - round(current_color[i]))

        if ([round(current_color[0]), round(current_color[1]), round(current_color[2])] != [round(target_color[0]*255), round(target_color[1]*255), round(target_color[2]*255)]):
            
            # Increase the color by 1/30 of its final value every refresh
            for i in range(3):
                if (round(target_color[i]*255) < round(current_color[i])):
                    current_color[i] -= (differenceColorAmount[i]/30)
                elif (round(target_color[i]*255) > round(current_color[i])):
                    current_color[i] += (differenceColorAmount[i]/30)


        # Checks if the values are valid
        clockColor = graphics.Color((255 if current_color[0] > 255 else (0 if current_color[0] < 0 else current_color[0])) * brightness, (255 if current_color[1] > 255 else (0 if current_color[1] < 0 else current_color[1])) * brightness, (255 if current_color[2] > 255 else (0 if current_color[2] < 0 else current_color[2])) * brightness)

        # Fade between subtexts
        if (fading == False and round(animationTime, 2) != animationIdle):
            animationTime += 0.01
        elif (fading == False and round(animationTime, 2) == animationIdle):
            # Start fading
            animationTime = 0
            fading = True

        if (fading):
            if (fadingIn):
                subOpacity += animationSpeed
                if (abs(round(subOpacity, 2)) == 1):                    
                    fadingIn = False
                    fading = False
            else:
                subOpacity -= animationSpeed
                if (abs(round(subOpacity, 2)) == 0):
                    fadingIn = True
                    if (len(subtexts) - 1 <= subtextIndex):
                        subtextIndex = 0
                    else:
                        subtextIndex += 1

        subtextOpacity = 180 * abs(0 if round(subOpacity, 2) < 0 else round(subOpacity, 2)) * brightness
        subTextColor = graphics.Color(subtextOpacity, subtextOpacity, subtextOpacity)

        # Time
        clock = datetime.now().strftime("%I:%M")
        ampm = datetime.now().strftime("%p")

        # Date
        date = datetime.today().strftime("%a, %b %d")
        subtexts[0] = date

        if (darkOutside):
            if (status == "off"):
                # Turn off display
                if (round(brightness, 2) != dimBrightness):
                    brightness -= 0.02
                display()
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
    except requests.exceptions.RequestException:
        canvas.Clear()

        clockColor = graphics.Color(200, 200, 200)
        subTextColor = graphics.Color(255, 0, 0)

        graphics.DrawText(canvas, font_1, getBigTextOffset(datetime.now().strftime("%I:%M")) + 1, 20, clockColor, datetime.now().strftime("%I:%M"))
        graphics.DrawText(canvas, font_2, getSmallTextOffset("No  internet"), 28, subTextColor, "No  internet")
       
        matrix.SwapOnVSync(canvas)
        time.sleep(0.01)
    except KeyboardInterrupt:
        sys.exit()
    except Exception as e:
        print(e)
