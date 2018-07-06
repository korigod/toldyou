import os
import logging
import hashlib
import opentimestamps
from opentimestamps.calendar import RemoteCalendar
from opentimestamps.core.op import OpAppend, OpSHA256
from opentimestamps.core.timestamp import Timestamp, DetachedTimestampFile
from opentimestamps.core.serialize import BytesSerializationContext
from opentimestamps.core.notary import (PendingAttestation,
                                        BitcoinBlockHeaderAttestation)


CALENDAR_URL = 'https://a.pool.opentimestamps.org'


def _get_root(timestamp):
    if timestamp.attestations:
        return timestamp
    else:
        for deeper_timestamp in timestamp.ops.values():
            return _get_root(deeper_timestamp)


def generate(msg_bytes):
    '''Generates certificate'''

    hashed_bytes = hashlib.new('sha256', msg_bytes).digest()
    file_timestamp = DetachedTimestampFile(OpSHA256(), Timestamp(hashed_bytes))

    nonce_appended_stamp = file_timestamp.timestamp.ops.add(OpAppend(os.urandom(16)))
    timestamp = nonce_appended_stamp.ops.add(OpSHA256())

    remote_calendar = RemoteCalendar(CALENDAR_URL)

    result = remote_calendar.submit(timestamp.msg, timeout=None)

    try:
        if isinstance(result, Timestamp):
            timestamp.merge(result)
        else:
            logging.debug(str(result))
    except Exception as error:
        logging.debug(str(error))

    return timestamp


def upgrade(timestamp):
    '''Upgrade the certificate to Bitcoin blockchain verified one if possible'''

    calendar = RemoteCalendar(CALENDAR_URL)

    root = _get_root(timestamp)

    if isinstance(list(root.attestations)[0], BitcoinBlockHeaderAttestation):
        logging.debug('Already is Bitcoin verified!')
        return False

    upgraded_timestamp = calendar.get_timestamp(root.msg)
    upgraded_root = _get_root(upgraded_timestamp)

    if not isinstance(list(upgraded_root.attestations)[0], BitcoinBlockHeaderAttestation):
        logging.debug("Still isn't Bitcoin verified!")
        return False

    root.merge(upgraded_timestamp)

    file_timestamp = DetachedTimestampFile(OpSHA256(), timestamp)

    ctx = BytesSerializationContext()
    file_timestamp.serialize(ctx)

    return ctx.getbytes()
