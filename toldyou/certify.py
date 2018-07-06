# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, you can obtain one at http://mozilla.org/MPL/2.0/.

import os
import logging
import hashlib
import opentimestamps
from opentimestamps.calendar import RemoteCalendar, CommitmentNotFoundError
from opentimestamps.core.op import OpAppend, OpSHA256
from opentimestamps.core.timestamp import Timestamp, DetachedTimestampFile
from opentimestamps.core.serialize import (BytesSerializationContext,
                                           BytesDeserializationContext)
from opentimestamps.core.notary import (PendingAttestation,
                                        BitcoinBlockHeaderAttestation)


CALENDAR_URL = 'https://a.pool.opentimestamps.org'


logging.basicConfig(level=logging.DEBUG)


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

    return file_timestamp


def upgrade(file_timestamp):
    '''Upgrade IN-PLACE the certificate to Bitcoin blockchain verified one if possible.'''

    timestamp = file_timestamp.timestamp

    calendar = RemoteCalendar(CALENDAR_URL)

    root = _get_root(timestamp)

    if isinstance(list(root.attestations)[0], BitcoinBlockHeaderAttestation):
        logging.debug('Already is Bitcoin verified!')
        return False

    try:
        upgraded_timestamp = calendar.get_timestamp(root.msg)
    except CommitmentNotFoundError:
        # TODO: check for the exact reason
        logging.debug("Still isn't Bitcoin verified!")
        return False

    upgraded_root = _get_root(upgraded_timestamp)

    if not isinstance(list(upgraded_root.attestations)[0], BitcoinBlockHeaderAttestation):
        logging.debug("Still isn't Bitcoin verified!")
        return False

    root.merge(upgraded_timestamp)

    return True


def serialize(timestamp):
    '''timestamp arg is Timestamp or DetachedTimestampFile'''
    ctx = BytesSerializationContext()
    timestamp.serialize(ctx)
    return ctx.getbytes()


def deserialize(file_timestamp_bytes):
    ctx = BytesDeserializationContext(file_timestamp_bytes)
    return DetachedTimestampFile.deserialize(ctx)
