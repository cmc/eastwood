import json
from os import getenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# TODO: Move config loading to shared object.
with open(getenv('CONFIG_PATH', '/src/config/config.json')) as config_data:
    config = json.load(config_data)

engine = create_engine("postgresql://{}:{}@{}:5432/{}".format(
    config['POSTGRES_USER'],
    config['POSTGRES_PASS'],
    config['POSTGRES_HOST'],
    config['POSTGRES_DB']),
    pool_pre_ping=True,
    pool_recycle=300
    )

Session = sessionmaker(bind=engine)

Base = declarative_base()
