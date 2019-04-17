import csv
import json
import logging
import os
import requests
import slacker
import time
from Levenshtein import distance
"""

Retrieves all domains from zonefiles.io - daily, parses them against the target monitoring brands, alerts on similar domains.

edit_dist = distance("shitmex.com", "bitmex.com")
logging.info(edit_dist)
edit_dist = distance("yoloswaggins.com","bitmex.com")
logging.info(edit_dist)
"""


class Eastwood(object):
    """ 
        Everything you need to keep safe in the world wide web
    """

    def __init__(self):
        """
        Load Config and things. 
        """
        with open('config/config.json') as config_data:  
            self.config = json.load(config_data)
            print(self.config)

    def send_to_slack(self, text):
	    data = {
		'text': str(text),
		'username': 'HAL',
		'icon_emoji': ':robot_face:'
	    }

	    response = requests.post(self.config['SLACK_WEBHOOK'], data=json.dumps(
		data), headers={'Content-Type': 'application/json'})

	    logging.info('Response: ' + str(response.text))
	    logging.info('Response code: ' + str(response.status_code))

    def monitor_brands(self):
	updates_only = True
	if updates_only:
	    ZF_URL = "{}{}{}{}".format(self.config['ZF_URL'], self.config['ZF_API_KEY'], "/updatedata/", self.config['ZF_ZONE'])
	    logging.info("Retrieving only new domains <24hrs: {}".format(ZF_URL))
	else:
	    ZF_URL = "{}{}{}{}".format(self.config['ZF_URL'], self.config['ZF_API_KEY'], "/full/", self.config['ZF_ZONE'])
	    logging.info("Retrieving all domains for this zone: {}".format(ZF_URL))

	r = requests.get(ZF_URL, verify=False)
	decoded_content = r.content.decode('utf-8')
	cr = csv.reader(decoded_content.splitlines(), delimiter=',')
	my_list = list(cr)


	while True:
	    logging.info("Retrieved {} domains.".format(len(my_list)))
	    for row in my_list:
		domain_name = row[0].split('.')[0]
		
		for brand in self.config['MONITORED_BRANDS']:
		    """ check if our brands are in the domain name, at all """
		    if brand in domain_name:
			logging.info("Brand name detected: {}".format(row))
                        self.send_to_slack("Brand name detected: {}".format(row))

		    """ check levenshtein distance """
                    if distance(str(domain_name), str(brand)) < 3:
			logging.info("Similar name (distance): {}".format(row))
			self.send_to_slack("Similar name (distance): {}".format(row))

	    logging.info("Sleeping for {}..".format(self.config['SLEEP_TIME']))
	    time.sleep(self.config['SLEEP_TIME'])

if __name__ == "__main__":
    logging.info("Eastwood is starting up...")
    e = Eastwood()
    e.monitor_brands()
