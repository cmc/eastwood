import csv
import json
import logging
import requests
import time

from db import Session, Base, engine
from db.models import Domain
from os import getenv
from Levenshtein import distance


class Eastwood(object):
    """
    Everything you need to keep safe in the world wide web
    Retrieves all domains from zonefiles.io - daily, parses them
    against the target monitoring brands, alerts on similar domains.
    """

    def __init__(self):
        logging.basicConfig()
        self.logger = logging.getLogger('Eastwood')
        self.logger.setLevel(logging.DEBUG)
        self.db = Session()

        existing_domains = self.db.query(Domain).all()
        if existing_domains:
            self.logger.info(existing_domains)

        """
        Load Config and things.
        """

        with open(getenv(
                 'CONFIG_PATH', '/src/config/config.json')) as config_data:
            self.config = json.load(config_data)

    def send_to_slack(self, text):
        data = {
            'text': str(text),
            'username': 'HAL',
            'icon_emoji': ':robot_face:'
        }

        response = requests.post(self.config['SLACK_WEBHOOK'], data=json.dumps(
                data), headers={'Content-Type': 'application/json'})

        self.logger.info('Response: ' + str(response.text))
        self.logger.info('Response code: ' + str(response.status_code))

    def monitor_brands(self):
        updates_only = True
        if updates_only:
            ZF_URL = "{}{}{}{}".format(self.config['ZF_URL'],
                                       self.config['ZF_API_KEY'],
                                       "/updatedata/",
                                       self.config['ZF_ZONE'])
            self.logger.info(
                "Retrieving only new domains <24hrs: {}".format(ZF_URL))
        else:
            ZF_URL = "{}{}{}{}".format(self.config['ZF_URL'],
                                       self.config['ZF_API_KEY'],
                                       "/full/",
                                       self.config['ZF_ZONE'])
            self.logger.info(
                "Retrieving all domains for this zone: {}".format(ZF_URL))

        r = requests.get(ZF_URL, verify=False)
        decoded_content = r.content.decode('utf-8')
        cr = csv.reader(decoded_content.splitlines(), delimiter=',')
        my_list = list(cr)
        maxc = 20
        counter = 0
        for item in my_list:
            print(item)
            counter += 1
            if counter == maxc:
                break

        while True:
            # There's a lot of cleanup to be done here. RE DB Transactions.

            self.logger.info("Retrieved {} domains.".format(len(my_list)))
            for row in my_list:
                domain_name = row[0].split('.')[0]

                for brand in self.config['MONITORED_BRANDS']:
                    """ check if our brands are in the domain name, at all """
                    if brand in domain_name:
                        self.logger.info("Brand name detected: {}".format(row))
                        self.logger.debug("Checking if Entry exists in db")
                        existing_domain = self.db.query(Domain).filter(
                            Domain.domain == row[0]).first()
                        if not existing_domain:
                            self.db.add(
                                Domain(row[0], 'match'))
                            self.db.commit()
                            try:
                                self.send_to_slack(
                                    "Brand name detected: {}".format(row))
                            except Exception as e:
                                self.logger.info(
                                    "ERROR Sending to slack! {}".format(
                                        e.message))
                            data = {'alerted': 'True'}
                            new_entry = self.db.query(Domain).filter(
                                Domain.domain == row[0]).first()
                            self.db.query(Domain).filter(
                               Domain.id == new_entry.id).update(data)
                            self.db.commit()

                    """ check levenshtein distance """
                    if distance(str(domain_name), str(brand)) < 3:
                        self.logger.info("Similar name (distance): {}".format(
                            row))

                        self.logger.debug("Checking if Entry exists in db")
                        existing_domain = self.db.query(Domain).filter(
                            Domain.domain == row[0]).first()
                        if not existing_domain:
                            self.db.add(
                                Domain(row[0], 'similar'))
                            self.db.commit()
                            try:
                                self.send_to_slack(
                                    "Similar name (distance): {}".format(row))
                            except Exception as e:
                                    self.logger.info(
                                        "ERROR Sending to slack! {}".format(
                                                                 e.message))
                            data = {'alerted': 'True'}
                            new_entry = self.db.query(Domain).filter(
                                Domain.domain == row[0]).first()
                            self.db.query(Domain).filter(
                                Domain.id == new_entry.id).update(data)
                            self.db.commit()
            self.logger.info(
                "Sleeping for {}..".format(self.config['SLEEP_TIME']))
            time.sleep(self.config['SLEEP_TIME'])


if __name__ == "__main__":
    Base.metadata.create_all(engine)
    e = Eastwood()
    e.logger.info("Eastwood is starting up...")
    e.monitor_brands()
