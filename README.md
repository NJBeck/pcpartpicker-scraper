# pcpartpicker-scraper

Scrapes the motherboard, cpu, or gpu sections of pcpartpicker.com for selected units
* Customizable using a config
* Select the types of units (select cpu, gpu and motherboards) you want (only works for first page of results for now)
* Units that drop below a defined price can trigger an email alert
* Add unique terms to exclude units you don't want alerts about
* Option to archive results to a mysql database
* To be run periodically using a task scheduler