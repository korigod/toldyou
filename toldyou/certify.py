import os
import logging
import hashlib
import opentimestamps
from opentimestamps.core.op import OpAppend, OpSHA256
from opentimestamps.core.timestamp import Timestamp, DetachedTimestampFile
from opentimestamps.calendar import RemoteCalendar


def generate(msg_bytes):
    '''Generates certificate'''

    hashed_bytes = hashlib.new('sha256', msg_bytes).digest()
    file_timestamp = DetachedTimestampFile(OpSHA256(), Timestamp(hashed_bytes))

    nonce_appended_stamp = file_timestamp.timestamp.ops.add(OpAppend(os.urandom(16)))
    timestamp = nonce_appended_stamp.ops.add(OpSHA256())

    calendar_uri = 'https://a.pool.opentimestamps.org'

    remote_calendar = RemoteCalendar(calendar_uri)

    result = remote_calendar.submit(timestamp.msg, timeout=None)

    try:
        if isinstance(result, Timestamp):
            timestamp.merge(result)
        else:
            logging.debug(str(result))
    except Exception as error:
        logging.debug(str(error))

    return timestamp
