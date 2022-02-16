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
from requests.packages.urllib3.exceptions import InsecureRequestWarning


class Eastwood(object):
    """
    Everything you need to keep safe in the world wide web
    Retrieves all domains from zonefiles.io - daily, parses them
    against the target monitoring brands, alerts on similar domains.
    """

    def __init__(self):
        logging.basicConfig()
        self.logger = logging.getLogger("Eastwood")
        self.logger.setLevel(logging.INFO)
        self.db_max_retries = 3
        self.db = Session()

        """
        Load Config and things.
        """

        with open(getenv("CONFIG_PATH", "/src/config/config.json")) as config_data:
            self.config = json.load(config_data)

    def get_db_entry(self, record):
        for i in range(0, self.db_max_retries):
            try:
                existing_domain = (
                    self.db.query(Domain)
                    .filter(Domain.domain == record["domain"])
                    .first()
                )
            except Exception as e:
                self.logger.info("(Attempt {} Error querying db {}".format(i, e))
                continue
            break
        return existing_domain

    def add_db_entry(self, record, similarity):
        for i in range(0, self.db_max_retries):
            try:
                self.db.add(Domain(record["domain"], similarity))
            except Exception as e:
                self.logger.info("(Attempt {} Error adding to db {}".format(i, e))
                self.db.rollback()
                continue
            self.db.commit()
            break
        return

    def update_db_entry(self, record):
        for i in range(0, self.db_max_retries):
            try:
                entry = (
                    self.db.query(Domain)
                    .filter(Domain.domain == record["domain"])
                    .first()
                )
                self.db.query(Domain).filter(Domain.id == entry.id).update(record)
            except Exception as e:
                self.logger.info("(Attempt {} Error updating {}".format(i, e))
                self.db.rollback()
                continue
            self.db.commit()
            break
        return

    def send_to_slack(self, record, webhook, match=False):
        # Add URL Defanging to prevent slack crawl.
        slack_msg = "Similar brand registration detected {}\n```".format(
            defang(record["domain"])
        )
        if match:
            slack_msg = "*Brand registration detected {}*\n```".format(
                defang(record["domain"])
            )
        for k, v in record.items():
            if k == "domain":
                continue
            if len(v) >= 1:
                if "," in v:
                    v = v.replace(",", "\n          ")
                slack_msg += "\n{}: {}".format(k.title(), v)
        slack_msg += "```"
        data = {
            "text": slack_msg,
            "username": "Eastwood Brand Monitor",
            "icon_emoji": ":male-detective:",
        }

        response = requests.post(
            webhook, data=json.dumps(data), headers={"Content-Type": "application/json"}
        )

        self.logger.debug("Response: " + str(response.text))
        self.logger.debug("Response code: " + str(response.status_code))

    def monitor_brands(self, updates_only=True):
        if updates_only:
            ZF_URL = "{}{}{}{}".format(
                self.config["ZF_URL"],
                self.config["ZF_API_KEY"],
                "/updatedata/",
                self.config["ZF_ZONE"],
            )
            self.logger.info("Retrieving only new domains <24hrs: {}".format(ZF_URL))
        else:
            ZF_URL = "{}{}{}{}".format(
                self.config["ZF_URL"],
                self.config["ZF_API_KEY"],
                "/fulldata/",
                self.config["ZF_ZONE"],
            )
            self.logger.info("Retrieving all domains for this zone: {}".format(ZF_URL))

        while True:
            try:
                r = requests.get(ZF_URL, verify=False, stream=True)

                for chunk in r.iter_lines(chunk_size=8096):
                    decoded_content = chunk.decode("utf-8")
                    self.logger.debug(decoded_content)
                    cr = csv.reader(decoded_content.splitlines(), delimiter=",")
                    my_list = list(cr)

                    # There's a lot of cleanup to be done here. RE DB Transactions.
                    self.logger.debug("Retrieved {} domains.".format(len(my_list)))
                    for row in my_list:
                        # Generic struct for results to update record.
                        # Since we don't know what we'lll actualy getb ack
                        try:
                            record = {
                                "domain": row[0],
                                "nsrecord": row[1],
                                "ipaddress": row[2],
                                "geo": row[3],
                                "webserver": row[5],
                                "hostname": row[6],
                                "dns_contact": row[7],
                                "alexa_traffic_rank": row[8],
                                "contact_number": row[9],
                            }
                        except IndexError:
                            self.logger.info("Error parsing result! {}".format(row))

                        # Remove empty results
                        record = {k: v for k, v in record.items() if v is not None}

                        # Strip TLD to compare
                        domain_name = row[0].split(".")[0]

                        for brand in self.config["MONITORED_BRANDS"]:
                            for keyword in brand["keywords"]:
                                """check if our brands are in the domain name,
                                at all"""
                                if keyword in domain_name:
                                    self.logger.info(
                                        "Brand name detected: {}".format(record)
                                    )
                                    self.logger.debug("Checking if Entry exists in db")

                                    existing_domain = self.get_db_entry(record)
                                    if not existing_domain:
                                        self.add_db_entry(record, "match")
                                        try:
                                            self.send_to_slack(
                                                record, brand["webhook"], True
                                            )
                                        except Exception as e:
                                            self.logger.info(
                                                "ERROR Sending to slack! {}".format(
                                                    e.message
                                                )
                                            )
                                        record.update({"alerted": "True"})
                                        self.update_db_entry(record)

                                """ check levenshtein distance """
                                if distance(str(domain_name), str(keyword)) < int(
                                    brand["distance"]
                                ):
                                    # record['distance'] = brand['distance']
                                    self.logger.info(
                                        "Similar name found with threshold ({}): {}".format(
                                            record["domain"], brand["distance"]
                                        )
                                    )
                                    self.logger.debug("Checking if Entry exists in db")
                                    existing_domain = self.get_db_entry(record)
                                    if not existing_domain:
                                        self.add_db_entry(record, "similar")

                                        # if we're backfilling we don't want to spam.
                                        if updates_only:
                                            try:
                                                self.send_to_slack(
                                                    record, brand["webhook"]
                                                )
                                            except Exception as e:
                                                self.logger.info(
                                                    "Slack exception {}".format(
                                                        e.message
                                                    )
                                                )

                                            record.update({"alerted": "True"})
                                    self.update_db_entry(record)
            except Exception as e:
                self.logger.info("Error Downloading File!: {}".format(e))
                continue
            self.logger.info("Sleeping for {}..".format(self.config["SLEEP_TIME"]))
            time.sleep(self.config["SLEEP_TIME"])


if __name__ == "__main__":
    Base.metadata.create_all(engine)
    e = Eastwood()
    if getenv("BACKFILL_RECORDS"):
        e.logger.info(
            "Eastwood has detected that you want to backfill all DNS entries, we reccomend you only run this a few times a day"
        )
        e.monitor_brands(updates_only=False)

    if getenv("YOLO_REQUESTS"):
        e.logger.info(
            "Eastwood has detected that you have turned off TLS certificate warnings, I too like to live dangerously"
        )
        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
    e.logger.info("Eastwood is starting up...")
    e.monitor_brands()
