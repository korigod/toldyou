# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, you can obtain one at http://mozilla.org/MPL/2.0/.

import pymongo
from pymongo import MongoClient


def get_bot_data():
    """Returns bot data Mongo collection"""

    client = MongoClient('mongo', 27017)
    db = client.toldyou_db
    collection = db.bot_data
    return collection
