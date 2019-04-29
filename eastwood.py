import csv
import json
import logging
import requests
import time

from defang import defang
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
        self.logger.setLevel(logging.INFO)
        self.db = Session()

        """
        Load Config and things.
        """

        with open(getenv(
                 'CONFIG_PATH', '/src/config/config.json')) as config_data:
            self.config = json.load(config_data)

    def send_to_slack(self, record, match=False):
        # Add URL Defanging to prevent slack crawl.
        slack_msg = "Similar brand registration detected {}\n```".format(
            defang(record['domain']))
        if match:
            slack_msg = "*Brand registration detected {}*\n```".format(
                defang(record['domain']))
        for k, v in record.items():
            if k == 'domain':
                continue
            if len(v) >= 1:
                if "," in v:
                    v = v.replace(",", "\n          ")
                slack_msg += '\n{}: {}'.format(k.title(), v)
        slack_msg += '```'
        data = {
            'text': slack_msg,
            'username': 'Eastwood Brand Monitor',
            'icon_emoji': ':male-detective:'
        }

        response = requests.post(self.config['SLACK_WEBHOOK'], data=json.dumps(
                data), headers={'Content-Type': 'application/json'})

        self.logger.debug('Response: ' + str(response.text))
        self.logger.debug('Response code: ' + str(response.status_code))

    def monitor_brands(self, updates_only=True):
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
                                       "/fulldata/",
                                       self.config['ZF_ZONE'])
            self.logger.info(
                "Retrieving all domains for this zone: {}".format(ZF_URL))

        while True:

            r = requests.get(ZF_URL, verify=False, stream=True)

            for chunk in r.iter_lines(chunk_size=8096):
                decoded_content = chunk.decode('utf-8')
                self.logger.debug(decoded_content)
                cr = csv.reader(decoded_content.splitlines(), delimiter=',')
                my_list = list(cr)

                # There's a lot of cleanup to be done here. RE DB Transactions.
                self.logger.debug("Retrieved {} domains.".format(len(my_list)))
                for row in my_list:
                    # Generic struct for results to update record.
                    # Since we don't know what we'lll actualy getb ack
                    try:
                        record = {
                            'domain': row[0],
                            'nsrecord': row[1],
                            'ipaddress': row[2],
                            'geo': row[3],
                            'webserver': row[5],
                            'hostname': row[6],
                            'dns_contact': row[7],
                            'alexa_traffic_rank': row[8],
                            'contact_number': row[9],
                        }
                    except IndexError:
                        self.logger.info("Error parsing result! {}".format(
                            row))

                    # Remove empty results
                    record = {k: v for k, v in record.items() if v is not None}

                    # Strip TLD to compare
                    domain_name = row[0].split('.')[0]

                    for brand in self.config['MONITORED_BRANDS']:
                        """ check if our brands are in the domain name,
                            at all """
                        if brand in domain_name:
                            self.logger.info("Brand name detected: {}".format(
                                record))
                            self.logger.debug("Checking if Entry exists in db")
                            existing_domain = self.db.query(Domain).filter(
                                Domain.domain == record['domain']).first()

                            if not existing_domain:
                                self.db.add(
                                    Domain(record['domain'], 'match'))
                                self.db.commit()

                                new_entry = self.db.query(Domain).filter(
                                    Domain.domain == record['domain']).first()

                                try:
                                    self.send_to_slack(record, True)
                                except Exception as e:
                                    self.logger.info(
                                        "ERROR Sending to slack! {}".format(
                                            e.message))
                                record.update({'alerted': 'True'})
                                self.db.query(Domain).filter(
                                    Domain.id == new_entry.id).update(record)
                                self.db.commit()

                        """ check levenshtein distance """
                        if distance(str(domain_name), str(brand)) < 3:
                            self.logger.info(
                                "Similar name (distance): {}".format(record))

                            self.logger.debug("Checking if Entry exists in db")
                            existing_domain = self.db.query(Domain).filter(
                                Domain.domain == record['domain']).first()
                            if not existing_domain:

                                self.db.add(
                                    Domain(record['domain'], 'similar'))
                                self.db.commit()

                                new_entry = self.db.query(Domain).filter(
                                    Domain.domain == record['domain']).first()

                                # if we're backfilling we don't want to spam.
                                if updates_only:
                                    try:
                                        self.send_to_slack(record)
                                    except Exception as e:
                                            self.logger.info(
                                                "Slack exception {}".format(
                                                                    e.message))

                                    record.update({'alerted': 'True'})
                                self.db.query(Domain).filter(
                                    Domain.id == new_entry.id).update(record)
                                self.db.commit()

            self.logger.info(
                    "Sleeping for {}..".format(self.config['SLEEP_TIME']))
            time.sleep(self.config['SLEEP_TIME'])


if __name__ == "__main__":
    Base.metadata.create_all(engine)
    e = Eastwood()
    e.logger.info("Eastwood is starting up...")
    e.monitor_brands()
