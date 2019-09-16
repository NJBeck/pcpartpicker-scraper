
# todo: 
# add error handling on the requests and rendering
# add more specific search terms particularly for cpu/gpu
# exclude other properties such as vendors
# check sites to make sure price has actually dropped
# use database to check for historic deals/trends

from bs4 import BeautifulSoup
from datetime import datetime
import re
import smtplib
import os
import configparser
import mysql.connector
from mysql.connector import Error
from requests_html import HTMLSession, HTML
# using requests_html because page uses javascript 
# (first run will download/install chromium to render the javascript)

pageURL = 'https://pcpartpicker.com/products/'

# dictionaries of tags for forming the url
moboSuffixes = {
    'z370': '128', 'z390': '135', 'z270': '119', 'z170': '110', 'h370': '130',
    'h310': '131', 'h270': '121', 'h170': '111', 'h110': '113', 'x299': '126',
    'b360': '129', 'b250': '120', 'b350': '124', 'b450': '133', 'x370': '123',
    'x399': '127', 'x470': '132'
}

cpuSuffixes = {
    'i5': '12', 'i7': '13', 'i3': '11', 'i9': '61', 'ryzen3': '62',
    'ryzen5': '60', 'ryzen7': '59'
}

gpuSuffixes = {
    '1050': '379', '1050 ti': '380', '1060 3gb': '378', '1060 6gb': '373',
    '1070': '369', '1070 ti': '415', '1080': '367', '1080 ti': '390',
    '1660': '439', '1660 ti': '438', '2060': '436', '2070': '425',
    '2080': '427', '2080 ti': '424', 'titan rtx': '435',
    'rx 560 - 1024': '395', '570': '392', '580': '391', '590': '431',
    'vega 56': '404', 'vega 64': '405', 'radeon vii': '437',
    'rx 560 - 896': '416',
}

unitSuffixes = {}

config = configparser.ConfigParser()
config.read('config.ini')

mysql_config={'host': config['mysql database']['host'],
    'user':config['mysql database']['username'],
    'passwd':config['mysql database']['password'],
    'database':config['mysql database']['database name'],
    'auth_plugin':config['mysql database']['auth_plugin'],
}
# form the URL from the lookingFor config and the dictionaries
lookingFor = config['price and terms']['lookingFor'].lower()
if lookingFor == 'cpu':
    unitSuffixes = cpuSuffixes
    pageURL += 'cpu/#s='
elif lookingFor == 'gpu':
    unitSuffixes = gpuSuffixes
    pageURL += 'video-card/#c='
else:
    unitSuffixes = moboSuffixes
    pageURL += 'motherboard/#c='

chosenSuffixes = config['price and terms']['units'].split(', ')
urlSuffixes = []
for suffix in chosenSuffixes:
    urlSuffixes.append(unitSuffixes[suffix])

#our final page url to scrape
pageURL = pageURL + ','.join(urlSuffixes) + '&sort=price' 
print('scraping '+ pageURL)

triggerPrice = float(config['price and terms']['triggerPrice'])

excludedUnits = config['price and terms']['excludedTerms'].split(', ')

# next few if statements are grabbing email info from environment variables
# if told to; otherwise, just take them straight from the config
sendingEmail = ''
if config['email info'].getboolean('usingEnvSendEmail'):
    sendingEmail = os.environ.get(config['email info']['sendingEmail'])
else: 
    sendingEmail = config['email info']['sendingEmail']

sendingPassword = ''
if config['email info'].getboolean('usingEnvPassword'):
    sendingPassword = os.environ.get(config['email info']['sendingPassword'])
else: 
    sendingPassword = config['email info']['sendingPassword']

receivingEmail = config['email info']['receivingEmail']
sendingPort = config['email info'].getint('sendingEmailPort')

# get our html after javascript has finished rendering
session = HTMLSession()
r = session.get(pageURL)
r.html.render(timeout=10, sleep=10)
source = r.html.html

soup = BeautifulSoup(source, 'lxml')

# names/prices have classes td__nameWrapper and td__price respectively
namematch = soup.find_all(class_='td__nameWrapper')
names = []
for name in namematch:
    item_name = name.text[:-4].strip()
    names.append(item_name)

pricematch = soup.find_all(class_='td__price')
prices = []
for price in pricematch:
    #strip any non numerals from price
    stripped = re.sub('[^0-9\.]','', price.text)
    if stripped:
        prices.append(float(stripped))

# generate dict of all name: price where price isnt N/A
cleanDict = {k: v for k, v in zip(names, prices)}
print(cleanDict)

#do mysql database logging if enabled
if config['mysql database']['database name']:
    try:
        mydb = mysql.connector.connect(**mysql_config)
        mycursor = mydb.cursor()

        def find_tables_like(table):
            # searches the database for an existing table for that item
            mycursor.execute(f'SHOW TABLES LIKE \"{table}\"')
            tables = []
            for table in mycursor:
                tables.append(table)
            return tuple(tables)

        def insert_price(table, price):
            # inserts the datetime and price into the table
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            query = f"INSERT INTO `{table}` (date, price) " \
                    f"VALUES(\'{now}\',{price})"
            mycursor.execute(query)
            mydb.commit()

        # check if tables of prices exist for each item
        for name, price in cleanDict.items():
            # convert spaces and dashes to underscores for mysql
            # name = name.replace(' ', "_").replace('-', "_")
            try:
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # if table doesnt exist then create it and insert date and price
                if not find_tables_like(name):
                    query = f'CREATE TABLE `{name}`(date DATETIME, ' \
                            'price DECIMAL(7, 2), PRIMARY KEY(date))'
                    mycursor.execute(query)
                insert_price(name, price)
            except Error as e:
                print(e)

        mydb.close()
        mycursor.close()
    except Error as e:
        print(e)
else:
    print('no mysql database')



# regex pattern for our exclusionary terms
pattern = "(" + ")|(".join(excludedUnits).lower() + ")"

def email_alert(alertDict):
    '''logs in and sends and email with the info for the found units'''
    with smtplib.SMTP('smtp.gmail.com', sendingPort) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(sendingEmail, sendingPassword)

        subject = 'motherboard price drop'
        body = ''
        for name in alertDict.keys():
            body += name + ' is at $' + str(alertDict[name]) + '\n'
        msg = f'Subject: {subject}\n\n{body}'
        
        smtp.sendmail(sendingEmail, receivingEmail, msg)


# generate dictionary of name: price which meets our criteria
alertDict = {}
for name in cleanDict.keys():
    if cleanDict[name] < triggerPrice:
        if not re.search(pattern, name.lower()):
            alertDict[name] = cleanDict[name]

if alertDict and config['email info']['sendEmail']:
    email_alert(alertDict)

