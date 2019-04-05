
# todo: 
# add error handling on the rendering
# generalize to other product sections/motherboards types
# exclude other properties such as vendors
# check sites to make sure price has actually dropped
# log data that is scraped to check for unusual deals

import requests
from bs4 import BeautifulSoup
import re
import smtplib
from requests_html import HTMLSession
# using requests_html because page uses javascript 
# (first run will download/install chromium to render the javascript)

pageURL = "https://pcpartpicker.com/products/motherboard/detailed-list/#c=128,135"
# url for z370 and z390 motherboards
triggerPrice = 100
# price which triggers an email if a matching unit price falls below
excludedUnits = []
# some case insensitive unit-unique terms to exclude units I don't care about
# example: 'pro4'

sendingEmail = ''
sendingPassword = ''
# email and password of the account you want to send from
# I suggest using app unique passwords hidden in environment variables

receivingEmail = ''
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

# urls = []
# for url in namematch:
# 		urls.append(url.a.get('href'))
# will probably use this eventually

pattern = "(" + ")|(".join(excludedUnits).lower() + ")"
# regex pattern for our exclusionary terms


fullDict = {k: v for k, v in zip(names, prices)}
cleanDict = {}
for name in fullDict.keys():
	if fullDict[name] != 'N/A':
		cleanDict[name] = fullDict[name]
# generate dict of all name: price where price isnt N/A

alertDict = {}
for name in cleanDict.keys():
	if cleanDict[name] < triggerPrice:
		if not re.search(pattern, name.lower()):
			alertDict[name] = cleanDict[name]
# generate dictionary of name: price which meets our criteria

def emailAlert(alertDict):
	with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
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


if alertDict:
	emailAlert(alertDict)
