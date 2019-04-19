from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.sql import func
from . import Base


class Domain(Base):
    """
        Domain Object Model.
        This schema will likely change often.
        id              Go Figure,
        domain          Actual Record
        simlarity       Similar vs Match
        status          Notes for action/ further use here later.
        alerted         Alerted or not
        time_created    Datetime when db entry was added
        time_updated    Datetime when db entry was updated
    """
    __tablename__ = 'domains'
    id = Column(Integer, primary_key=True)
    domain = Column(String(255), unique=True)
    similarity = Column(String(255))
    status = Column(String(255))
    alerted = Column(String(255))
    time_created = Column(DateTime(timezone=True),
                          server_default=func.now())
    time_updated = Column(DateTime(timezone=True), onupdate=func.now())

    def __init__(self, domain, similarity):
        self.domain = domain
        self.similarity = similarity

    def __repr__(self):
        return '{}'.format(self.id)
