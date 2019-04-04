
# todo: 
# work with multiples below price
# add error handling on the rendering
# generalize to other product sections
# exclude other properties such as vendors
# check sites to make sure price has actually dropped
# log data that is scraped to check for unusual deals

import requests
from bs4 import BeautifulSoup
import re
import smtplib
import os
from requests_html import HTMLSession
# using requests_html because page uses javascript 
#(first run will download/install chromium to render the javascript)

pageURL = "https://pcpartpicker.com/products/motherboard/detailed-list/#c=128,135"
# url for z370 and z390 motherboards
triggerPrice = 110.0
# price which triggers an email if a matching unit price falls below
excludedUnits = ['phantom gaming 4', 'mortar', 'ds3h', 'z370p d3', 'a pro']
# some case insensitive unit-unique terms to exclude units I don't care about

sendingEmail = os.environ.get('USER_EMAIL')
sendingPassword = os.environ.get('USER_PASSWORD')
# email and password hidden in os environment variables

receivingEmail = sendingEmail
# i use the same email to receive but it can of course be changed




session = HTMLSession()
r = session.get(pageURL)
r.html.render()
source = r.html.html
# returns our html after javascript has finished rendering

soup = BeautifulSoup(source, 'lxml')

# relevant info is tagged td and have classes tdname and tdprice respectively
namematch = soup.find_all('td', class_='tdname')
names = []
for name in namematch:
	names.append(name.a.text)


pricematch = soup.find_all('td', class_='tdprice')
prices = []
for price in pricematch:
	if price.text:
		prices.append(float(price.text[1:]))
	else:
		prices.append('N/A')

urls = []
for url in namematch:
		urls.append(url.a.get('href'))

def emailAlert(name):
	with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
		smtp.ehlo()
		smtp.starttls()
		smtp.ehlo()
		smtp.login(sendingEmail, sendingPassword)

		subject = 'motherboard price drop'
		body = name + ' has dropped below $' + str(triggerPrice)
		msg = f'Subject: {subject}\n\n{body}'

		smtp.sendmail(sendingEmail, receivingEmail, msg)


for price in prices:
	if price != 'N/A' and price < triggerPrice:
		name = names[prices.index(price)]
		
		pattern = "(" + ")|(".join(excludedUnits).lower() + ")"

		if not re.search(pattern, name.lower()):
			emailAlert(name)
		
