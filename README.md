# Erlends Home Assistant Configuration

### The config is due for a cleanup, with lots off commented out code.
### Some files are pretty old and could be organized a lot better with packages.



### Some files are not on github due to security reasons.
#### Also, the code is in a good mix of norwegian and english, but should be readable. 

## Some features:

#### Climate controlled by hourly price, from Nordpool and Tibber integration
If price is peaking, the temperature around the house is decreased by one degree celcius. If the price is gaining the next hour, increase the temperature by one degree.
This helps with lowering the power consumption in the most expensive hours.

#### Automatic alarm
The alarm is armed whenever we leave the house or go to sleep, based on device trackers and sleeping sensors, boiled down to a template alarm sensor.

#### Presence based lights
(Almost) all lights are based on motion sensors and magnet sensors, and will turn on and dim to a specific level, depending on different states.

#### Basic Children tracking
This sound kinda sketchy.
Track if the toddlers are asleep based on when we enter their rooms, or if they are in kindergarden, based on if the device trackers enter the kindergarden zone.
This is used for:
- Quiet time. Turn down the speakers for TTS announcements when the kids are asleep 
- Turn on the light in our bedroom if the kids leave their rooms at night.  
- Notify us if we forgot to lock the stair gates so they can't fall down the stairs
- Notify us if no one has picked them up from kindergarden before it closes.


#### Smart watch control
Selfmade watchface with tasker integration that triggers some webhooks and actionable notifications in Home Assistant that does the following:
- Dim the lights in some occupied rooms to desired light level.
- Toggle the garage
- Toggle the curtains
- Turn on/off the bed blanket heater

#### Other:
- Stock price notifications using FinnHub.io API
- Mail delivery days notifications.
- Waste collection notifications
- Game timer. After hunting, game birds are supposed to hang for 40 'daydegrees'. This package appendes the temperature for each hour, and notifies me when the bird is ready for the freezer.

## Specs

- Aqara motion sensors and magnet sensors
- IKEA Trådfri / Hue / Namron lights, switches and bulbs
- Aqara and 433mhz temperature and humidity sensors
- Xiaomi water leakage sensors and smoke detectors.
- A-OK Curtain controllers from AliExpress, controlled with ESP32.
- ESP32-based light strips
- ESP32-based garage door and garage occupied sensor.
- Yale Doorman smartlock
- Xiaomi Roborock S5 Vacuum cleaner
- Sonoff controlled bathroom fan, turns on when humidity is high.
- Ikea Trådfri switch for bed blanket warmer 
- Ikea Trådfri switches for electric car heater, with notification before we go to bed if it's freezing overnight.
- Ring Doorbell
- Google Nest speakers for announcement and multi room music.
- Ender 3 3D Printer connected with Octoprint.
- Tibber for power management. (Use Referral code https://invite.tibber.com/11541ba9 for 50 EUR bonus for smarthome equipment)
- MiFlora sensors for plants
- Power monitoring of washer and dryer for notifications when the laundry is done.


## Screenshots: 

![Home](screenshotHome.png)
![Security](screenshotSecurity.png)
![Printer](screenshotPrinter.png)
![Power](screenshotpower.png)
![Stocks](screenshotStocks.png)
