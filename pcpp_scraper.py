
# todo: 
# add parallelization for scraping multiple pages
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
import requests_html
import concurrent.futures
# using requests_html because page uses javascript 
# (first run will download/install chromium to render the javascript)

config = configparser.ConfigParser()
config.read('config.ini')

def form_urls():
    ''' to return a list of URLs to be scraped
        example: ['https://pcpartpicker.com/products/motherboard/#c=128,135',
                 'https://pcpartpicker.com/products/cpu/#s=60,59'] '''

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

    URLs = []
    moboURLsuffixes = []
    cpuURLsuffixes = []
    gpuURLsuffixes = []
    terms = config['price and terms']['units'].split(', ')
    for term in terms:
        if term in moboSuffixes.keys():
            moboURLsuffixes.append(moboSuffixes[term])
        elif term in cpuSuffixes.keys():
            cpuURLsuffixes.append(cpuSuffixes[term])
        elif term in gpuSuffixes.keys():
            gpuURLsuffixes.append(gpuSuffixes[term])
    if moboURLsuffixes:
        moboURL = pageURL + 'motherboard/#c=' + ','.join(moboURLsuffixes) + '&sort=price'
        URLs.append(moboURL)
    if cpuURLsuffixes:
        cpuURL = pageURL + 'cpu/#s=' + ','.join(cpuURLsuffixes) + '&sort=price'
        URLs.append(cpuURL)
    if gpuURLsuffixes:
        gpuURL = pageURL + 'video-card/#c=' + ','.join(gpuURLsuffixes) + '&sort=price'
        URLs.append(gpuURL)
    return URLs

def scrape(source):
    '''return a dictionary of name: price from the URL given'''
    s = source.html
    soup = BeautifulSoup(s, 'lxml')

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

    # generate dict of all name: price where price isnt null
    priceDict = {k: v for k, v in zip(names, prices)}
    return priceDict

def mysql_log(priceDict):
    '''for each item it creates a table of datetime: price'''
    try:
        mysql_config={'host': config['mysql database']['host'],
            'user':config['mysql database']['username'],
            'passwd':config['mysql database']['password'],
            'database':config['mysql database']['database name'],
            'auth_plugin':config['mysql database']['auth_plugin'],
        }

        mydb = mysql.connector.connect(**mysql_config)
        mycursor = mydb.cursor()

        def find_tables_like(table):
            '''searches the database for an existing table for that item'''
            mycursor.execute(f'SHOW TABLES LIKE \"{table}\"')
            tables = []
            for table in mycursor:
                tables.append(table)
            return tuple(tables)

        def insert_price(table, price):
            '''inserts the datetime and price into the table'''
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            query = f"INSERT INTO `{table}` (date, price) " \
                    f"VALUES(\'{now}\',{price})"
            mycursor.execute(query)
            mydb.commit()

        # check if tables of prices exist for each item
        for name, price in priceDict.items():
            # convert spaces and dashes to underscores for mysql
            # name = name.replace(' ', "_").replace('-', "_")
            try:
                # if table doesnt exist then create it and insert date and price
                if not find_tables_like(name):
                    query = f'CREATE TABLE `{name}`(date DATETIME, ' \
                            'price DECIMAL(7, 2), PRIMARY KEY(date))'
                    mycursor.execute(query)
                insert_price(name, price)
            except mysql.connector.Error as e:
                print(e)
        mycursor.close()
        mydb.close()
        
    except mysql.connector.Error as e:
        print(e)

def get_sending_email():
    '''gets target email address from config or environment variables'''
    if config['email info']['sendingEmail']:
        sendingEmail = config['email info']['sendingEmail']
    else: 
        sendingEmail = os.environ.get('USER_EMAIL')
    return sendingEmail

def get_sending_pwd():
    '''gets target password from config or environment variables'''
    if config['email info']['sendingPassword']:
        sendingPassword = config['email info']['sendingPassword']
    else: 
        sendingPassword = os.environ.get('EMAIL_PASSWORD')
    return sendingPassword

def alert_dict(priceDict):
    '''generates the dictionary of items which meet the criteria of below the 
    trigger price and dont match exclusion terms'''
    # regex pattern for our exclusionary terms
    excludedUnits = config['price and terms']['excludedTerms'].split(', ')
    pattern = "(" + ")|(".join(excludedUnits).lower() + ")"

    alertDict = {}
    triggerPrice = float(config['price and terms']['triggerPrice'])
    for name in priceDict.keys():
        if priceDict[name] < triggerPrice:
            if not re.search(pattern, name.lower()):
                alertDict[name] = priceDict[name]
    return alertDict

def email_alert(alertDict, sendingEmail, sendingPassword, receivingEmail, sendingPort, SMTPHost):
    '''logs in and sends and email with the info for the found units'''
    with smtplib.SMTP(SMTPHost, sendingPort) as smtp:
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

def email():
    if config['email info']['sendEmail']:
        receivingEmail = config['email info']['receivingEmail']

        if config['email info']['sendingPort']:
            sendingPort = config['email info'].getint('sendingEmailPort')
        else: 
            sendingPort = 587
        if config['email info']['SMTPHost']:
            SMTPHost = config['email info']['SMTPHost']
        else:
            SMTPHost = 'smtp.gmail.com'
        
        sendingEmail = get_sending_email()

        sendingPwd = get_sending_pwd()

        alertDict = alert_dict(priceDicts)
        if alertDict:
            email_alert(alertDict, sendingEmail, sendingPwd, receivingEmail, sendingPort, SMTPHost)

def get_render(url):
    session = requests_html.HTMLSession()
    r = session.get(url)
    r.html.render(timeout=10, sleep=5)
    return r.html

def render_all (urls):
    with concurrent.futures.ProcessPoolExecutor() as exec:
        results = exec.map(get_render, URLs)
        return results

if __name__ == '__main__':
    URLs = form_urls()
    print('scraping ' + ', '.join(URLs))

    renderResults = render_all(URLs)

    priceDicts = {}
    for result in renderResults:
        priceDict = scrape(result)
        priceDicts.update(priceDict)
    print(priceDicts)

    if config['mysql database']['database name']:
            mysql_log(priceDict)
    else:
        print('no mysql database')

    email()



