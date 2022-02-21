from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.sql import func
from . import Base


class Domain(Base):
    """
    Domain Object Model.
    id                  DB Record ID.
    domain              Domain name.
    nsrecord            Authoratative nameserver for domain.
    geoip               GeoIP location.
    geohtml             Location based on DOM / HTML.
    webserver           Version string from webserver.
    hostname            Server hostname.
    dns_contact         Abuse ARN contact email.
    alexa_traffic_rank  Traffic rank.
    simlarity           Similar vs match.
    status              Notes for action/exclusion.
    threshold           Threshold distance used to determine if match.
    alerted             If webhook has sent alert.
    time_created        Datetime when db entry was added.
    time_updated        Datetime when db entry was updated.
    """

    __tablename__ = "domains"
    id = Column(Integer, primary_key=True)
    domain = Column(String(255), unique=True)
    nsrecord = Column(String(255))
    ipaddress = Column(String(255))
    geo = Column(String(255))
    webserver = Column(String(255))
    hostname = Column(String(255))
    dns_contact = Column(String(255))
    alexa_traffic_rank = Column(String(255))
    contact_number = Column(String(255))
    similarity = Column(String(255))
    threshold = Column(String(255))
    status = Column(String(255))
    alerted = Column(String(255))
    time_created = Column(DateTime(timezone=True), server_default=func.now())
    time_updated = Column(DateTime(timezone=True), onupdate=func.now())

    def __init__(self, domain, similarity, status):
        self.domain = domain
        self.similarity = similarity
        self.status = status

    def __repr__(self):
        return "{}".format(self.id)
