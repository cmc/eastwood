from sqlalchemy.sql import func
from . import db


class Domain(db.Model):
    """
        Domain Object Model. Derp.
        TODO.
    """

    id = db.Column(db.Integer, primary_key=True)
    domain = db.Column(db.String(255), unique=True)
    time_created = db.Column(db.DateTime(timezone=True),
                             server_default=func.now())
    time_updated = db.Column(db.DateTime(timezone=True), onupdate=func.now())

    def __init__(self, domain):
        self.domain = domain

    def __repr__(self):
        return '{}'.format(self.id)
