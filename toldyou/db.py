import pymongo
from pymongo import MongoClient


def get_bot_data():
    """Returns bot data Mongo collection"""

    client = MongoClient('mongo', 27017)
    db = client.toldyou_db
    collection = db.bot_data
    return collection
