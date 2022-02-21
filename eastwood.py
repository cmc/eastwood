import csv
import json
import logging
import requests
import time
import traceback

from defang import defang
from db import Session, Base, engine
from db.models import Domain
from pprint import pformat
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
                self.logger.error("(Attempt {} Error querying db {}".format(i, e))
                self.logger.error(traceback.format_exc())
                self.db.rollback()
                continue
            break
        return existing_domain

    def add_db_entry(self, record, similarity, status="monitor"):
        for i in range(0, self.db_max_retries):
            try:
                self.db.add(Domain(record["domain"], similarity, status))
            except Exception as e:
                self.logger.info("(Attempt {} Error adding to db {}".format(i, e))
                self.logger.error(traceback.format_exc())
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
                self.logger.error(traceback.format_exc())
                self.db.rollback()
                continue
            self.db.commit()
            break
        return

    def check_exclusion(self, domain, brand):
        for exclusion in brand["exclusions"]:
            if domain == exclusion:
                self.logger.info(
                    "Ignoring domain: {}, is excluded due to {} keyword exclusion.".format(
                        domain, exclusion
                    )
                )
                return True
        return False

    def send_to_slack(self, record, webhook, match=False):
        slack_msg = "Similar brand registration detected {}\n```".format(
            defang(record["domain"])
        )
        if match:
            slack_msg = "*Brand registration detected {}*\n```".format(
                defang(record["domain"])
            )

        if record.items:
            for k, v in record.items():
                if k == "domain" or k == "threshold":
                    continue
                if len(v) >= 1:
                    if "," in v:
                        v = v.replace(",", "\n          ")
                    slack_msg += "\n{}: {}".format(k.title(), v)
        else:
            slack_msg += "No additional registration information found."

        slack_msg += "\n```"
        data = {
            "text": slack_msg,
            "username": self.config["SLACK"]["username"],
            "icon_emoji": self.config["SLACK"]["icon_emoji"],
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
            self.logger.info("Retrieving only new domains in the last <24hrs")
        else:
            ZF_URL = "{}{}{}{}".format(
                self.config["ZF_URL"],
                self.config["ZF_API_KEY"],
                "/fulldata/",
                self.config["ZF_ZONE"],
            )
            self.logger.info("Retrieving all domains this could take some time...")

        while True:
            try:
                r = requests.get(ZF_URL, verify=False, stream=True)

                for chunk in r.iter_lines(chunk_size=8096):
                    decoded_content = chunk.decode("utf-8")
                    self.logger.debug(decoded_content)

                    cr = csv.reader(decoded_content.splitlines(), delimiter=",")
                    domain_list = list(cr)
                    self.logger.debug("Retrieved {} domains.".format(len(domain_list)))
                    for row in domain_list:
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
                            self.logger.error(
                                "Error parsing result! {} See if ZF has updated CSV Schema?".format(
                                    row
                                )
                            )

                        record = {
                            k: v for k, v in record.items() if v is not None
                        }  # Remove empty results
                        domain_name = row[0].split(".")[0]  # Strip TLD to compare

                        for brand in self.config["MONITORED_BRANDS"]:
                            for keyword in brand["keywords"]:
                                if keyword in domain_name:
                                    self.logger.info(
                                        "Match found! {} matches keyword {}.".format(
                                            defang(row[0]), keyword
                                        )
                                    )
                                    self.logger.debug(pformat(record))

                                    self.logger.debug(
                                        "Checking if Entry exists in exclusions"
                                    )
                                    excluded = self.check_exclusion(row[0], brand)
                                    if excluded:
                                        self.logger.info(
                                            "Skipping {} record is excluded.".format(
                                                defang(row[0])
                                            )
                                        )

                                    self.logger.debug("Checking if Entry exists in db")
                                    existing_domain = self.get_db_entry(record)
                                    if existing_domain:
                                        self.logger.info(
                                            "Skipping {} record exists in DB.".format(
                                                defang(row[0])
                                            )
                                        )

                                    if not existing_domain:
                                        if not excluded:
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
                                        self.add_db_entry(record, "match", "exclude")

                                if distance(str(domain_name), str(keyword)) < int(
                                    brand["threshold"]
                                ):
                                    record["threshold"] = brand["threshold"]

                                    self.logger.info(
                                        "Similar name found with threshold of {} {}".format(
                                            brand["threshold"], defang(record["domain"])
                                        )
                                    )

                                    self.logger.debug("Checking if entry exists in DB")
                                    existing_domain = self.get_db_entry(record)
                                    if existing_domain:
                                        self.logger.info(
                                            "Skipping {} record exists in DB.".format(
                                                defang(row[0])
                                            )
                                        )

                                    if not existing_domain:
                                        self.add_db_entry(record, "similar")
                                        if updates_only:
                                            try:
                                                self.logger.debug(
                                                    "Sending {} to Slack".format(record)
                                                )
                                                self.send_to_slack(
                                                    record, brand["webhook"]
                                                )
                                            except Exception as e:
                                                self.logger.error(
                                                    traceback.format_exc()
                                                )

                                            record.update({"alerted": "True"})
                                    self.update_db_entry(record)
            except Exception as e:
                self.logger.error(traceback.format_exc())
                continue
            self.logger.info(
                "Processing complete sleeping for {}..".format(
                    self.config["SLEEP_TIME"]
                )
            )
            time.sleep(self.config["SLEEP_TIME"])


if __name__ == "__main__":
    Base.metadata.create_all(engine)
    e = Eastwood()
    if getenv("BACKFILL_RECORDS"):
        e.logger.info(
            "Eastwood has detected that you want to backfill all DNS entries, I recommend you only run this once."
        )
        e.monitor_brands(updates_only=False)

    if getenv("YOLO_REQUESTS"):
        e.logger.info(
            "Eastwood has detected that you have turned off TLS certificate warnings, I too like to live dangerously."
        )
        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

    e.logger.info("Eastwood is starting up...")
    e.monitor_brands()
