import requests
import urllib3
import xmltodict
import time
import adafruit_dht
import board
import sys
import datetime
import gspread
from dateutil import tz, parse
from oauth2client.service_account import ServiceAccountCredentials

DHT_TYPE = adafruit_dht.DHT22
DHT_PIN = board.D2
dhtDevice = DHT_TYPE(DHT_PIN)

GDOCS_OAUTH_JSON = 'temperaturelogging-284906-8b19fb149fd1.json'
GDOCS_SPREADSHEET_NAME = 'TemperatureLog'
 
# How long to wait (in seconds) between measurements.
FREQUENCY_SECONDS = 600
url = 'https://api.synopticdata.com/v2/stations/latest?stid=E0597&token=37f690b5ffe34e92b8f68041a7197167'


def login_open_sheet(oauth_key_file, spreadsheet):
    """Connect to Google Docs spreadsheet and return the first worksheet."""
    try:
        scope =  ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        credentials = ServiceAccountCredentials.from_json_keyfile_name(oauth_key_file, scope)
        gc = gspread.authorize(credentials)
        worksheet = gc.open(spreadsheet).sheet1 # pylint: disable=redefined-outer-name
        return worksheet
    except Exception as ex: # pylint: disable=bare-except, broad-except
        print('Unable to login and get spreadsheet.  Check OAuth credentials, spreadsheet name, \
        and make sure spreadsheet is shared to the client_email address in the OAuth .json file!')
        print('Google sheet login failed with error:', ex)
        return None


def CtoF(celsiusValue):
    return celsiusValue * (9/5) + 32


print('Logging sensor measurements to {0} every {1} seconds.'.format(GDOCS_SPREADSHEET_NAME, FREQUENCY_SECONDS))
print('Press Ctrl-C to quit.')
worksheet = None

while True:
    if worksheet is None:
        worksheet = login_open_sheet(GDOCS_OAUTH_JSON, GDOCS_SPREADSHEET_NAME)
        if worksheet is None:
            print("Trying again in 20 seconds")
            time.sleep(20)        
            continue
    try:
        response = requests.get(url)
        data = response.json()
    except:
        response = None
        data = None
    insideObservationTime = time.strftime('%Y-%m-%d %H:%M', time.localtime(time.time()))
    try:
        insideTemperature = int(CtoF(dhtDevice.temperature))
        insideHumidity = int(dhtDevice.humidity)
        print(str(insideObservationTime) + ' Temperature: ' + str(insideTemperature), end='\r')
    except RuntimeError as e:
        print(str(insideObservationTime) + " Reading from DHT failure: ", e.args)
        print("Trying again in 20 seconds")
        time.sleep(20)
        continue

    if insideTemperature is None or insideTemperature is None:
        print(str(insideObservationTime) + " Inside readings invalid. Trying again in 20 seconds")
        time.sleep(20)
        continue

    if data:
        observation = data['STATION'][0]['OBSERVATIONS']
        outsideObservationTime = parse(observation['air_temp_value_1']['date_time']).astimezone(tz.gettz('America/Los Angeles')).strftime('%Y-%m-%d %H:%M')
        outsideTemperature = int(CtoF(observation['air_temp_value_1']['value']))
        outsideHumidity = int(observation['relative_humidity_value_1']['value'])
        outsideDewpoint = int(CtoF(observation['dew_point_temperature_value_1d']['value']))
        try:
            worksheet.append_row((insideObservationTime, insideTemperature, insideHumidity, outsideObservationTime, outsideTemperature, outsideHumidity, insideTemperature - outsideTemperature))
        except: # pylint: disable=bare-except, broad-except
            # Error appending data, most likely because credentials are stale.
            # Null out the worksheet so a login is performed at the top of the loop.
            print(str(insideObservationTime) + ' Append error, logging in again')
            worksheet = None
            time.sleep(20)
            continue

    time.sleep(FREQUENCY_SECONDS)

