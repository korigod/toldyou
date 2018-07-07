# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, you can obtain one at http://mozilla.org/MPL/2.0/.

import os
import sys
import threading
import signal
import time
import logging
import datetime as dt
from enum import Enum
from uuid import uuid4

from bson.binary import Binary
from telegram import InlineQueryResultArticle, InputTextMessageContent, ParseMode
from telegram.ext import (Updater, Filters, CommandHandler, InlineQueryHandler,
                          MessageHandler, ConversationHandler)
from telegram.utils.helpers import escape_markdown

import db
import certify

DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S UTC'

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.DEBUG)
logger = logging.getLogger(__name__)

bot_data = db.get_bot_data()

upgrade_thread_stop_event = threading.Event()


class StampUpgradeThread(threading.Thread):
    def __init__(self, mongo_collection, event_to_stop, telegram_updater):
        super().__init__()
        self.collection = mongo_collection
        self.stop = event_to_stop
        self.updater = telegram_updater

    def run(self):
        while not self.stop.is_set():
            start_time = time.perf_counter()
            for record in self.collection.find({'blockchained': None}):
                upgraded = upgrade_record_certificate(record)
                if upgraded:
                    link = get_certificate_link_text(record)
                    text = ('_Your phrase was verified by Bitcoin '
                            'blockchain:_\n{}\n{}'.format(record['text'], link))
                    self.updater.bot.send_message(record['user'],
                                                  text,
                                                  parse_mode=ParseMode.MARKDOWN,
                                                  disable_web_page_preview=True)
                if self.stop.is_set():
                    return
            # Check certificates once in ten minutes
            time.sleep(max(0, start_time + 600 - time.perf_counter()))


def signal_handler(signum, frame):
    upgrade_thread_stop_event.set()
    sys.exit(2)


def store_phrase(user, phrase):
    """user should be telegram.User object"""
    timestamp = certify.generate(bytes(phrase, 'UTF-8'))
    record = {'user': user.id,
              'username': user.username,
              'user_full_name': user.full_name,
              'created': dt.datetime.utcnow(),
              'text': phrase,
              'type': 'PHRASE',
              'stamp': Binary(certify.serialize(timestamp)),
              'blockchained': None}
    inserted_id = bot_data.insert_one(record)
    return inserted_id


def get_users_stored_records(user_id):
    """Returns Mongo cursor"""
    records = bot_data.find({'user': user_id})
    return records


def delete_all_users_records(user_id):
    bot_data.delete_many({'user': user_id})


def timestamp_to_link(timestamp_binary):
    """Returns markdown certificate link"""
    stamp_hex = timestamp_binary.hex()
    url = 'https://opentimestamps.org/info/?{}'.format(stamp_hex)
    certificate_text = '[Blockchain certificate]({})'.format(url)
    return certificate_text


def get_certificate_link_text(record):
    """Returns a markdown link or a notice that it's pending."""
    if record['blockchained'] is not None:
        return timestamp_to_link(record['stamp'])
    else:
        return '_Blockchain verification is pending_'


def upgrade_record_certificate(record):
    """
    Upgrades the record IN-PLACE and returns whether the record was upgraded.
    Performs database update as well. If the record was already blockchain
    verified, returns False.
    """
    upgraded = False

    if record['blockchained'] is None:
        timestamp = certify.deserialize(record['stamp'])
        if certify.upgrade(timestamp) is True:
            upgraded = True
            dt_now = dt.datetime.utcnow()
            timestamp_binary = certify.serialize(timestamp)
            record['blockchained'] = dt_now
            record['stamp'] = timestamp_binary
            bot_data.update_one({'_id': record['_id']}, {
                                '$set': {
                                    'blockchained': dt_now,
                                    'stamp': Binary(timestamp_binary)
                                }})
    return upgraded


def start_command(bot, update):
    update.message.reply_text('Hi! Send me some text to store and verify or use '
                              '/list command to list already stored phrases. '
                              'Please note: this is an alpha version, your data '
                              'can be lost.')


def store_phrase_handler(bot, update):
    user = update.message.from_user
    update.message.reply_text('Got it!')
    store_phrase(user, update.message.text)


def list_command(bot, update):
    user_id = update.message.from_user.id
    users_records = get_users_stored_records(user_id)

    if users_records.count() == 0:
        update.message.reply_text('Nothing is stored yet!')

    else:
        update.message.reply_text('Here we go:')

        for record in users_records:
            if record['blockchained'] is None:
                upgrade_record_certificate(record)

            certificate_text = get_certificate_link_text(record)
            text = '_{}:_\n{}\n{}'.format(record['created'].strftime(DATETIME_FORMAT),
                                          record['text'],
                                          certificate_text)
            update.message.reply_text(text,
                                      parse_mode=ParseMode.MARKDOWN,
                                      disable_web_page_preview=True)


def delete_all_command(bot, update):
    update.message.reply_text('Type uppercase YES to delete all the records, '
                              'anything else to cancel.')
    return 'DELETE_ALL_RECORDS'


def delete_all_records_handler(bot, update):
    message = update.message.text
    if message == 'YES':
        user_id = update.message.from_user.id
        delete_all_users_records(user_id)
        update.message.reply_text('All stored records have been deleted.')
    else:
        update.message.reply_text('Deleting is cancelled.')
    return ConversationHandler.END


def inline_query(bot, update):
    user = update.inline_query.from_user
    user_records = get_users_stored_records(user.id)

    if user.username:
        username_to_mention = '@' + user.username
    else:
        username_to_mention = user.first_name + user.last_name

    # Renders to @username mention
    user_mention = '[{}](tg://user?id={})'.format(username_to_mention, user.id)

    results = []
    for record in user_records:
        record_created_dt_str = record['created'].strftime(DATETIME_FORMAT)

        if record['blockchained'] is None:
            upgrade_record_certificate(record)
        certificate_text = get_certificate_link_text(record)

        text_to_send = '{} told at *{}*:\n{}\n{}'.format(user_mention,
                                                         record_created_dt_str,
                                                         record['text'],
                                                         certificate_text)

        message = InputTextMessageContent(text_to_send,
                                          parse_mode=ParseMode.MARKDOWN,
                                          disable_web_page_preview=True)

        result = InlineQueryResultArticle(id=uuid4(),
                                          title=record['text'],
                                          description=record_created_dt_str,
                                          input_message_content=message)

        results.append(result)

    update.inline_query.answer(results)


def cancel_command(bot, update):
    pass


def error(bot, update, error):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, error)


def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    updater = Updater(os.environ['TELEGRAM_BOT_TOKEN'])
    dp = updater.dispatcher

    dp.add_handler(CommandHandler('start', start_command))
    dp.add_handler(CommandHandler('list', list_command))

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('delete_all', delete_all_command)],

        states={
            'DELETE_ALL_RECORDS': [MessageHandler(Filters.text, delete_all_records_handler)]
        },
        fallbacks=[CommandHandler('cancel', cancel_command)]
    )

    dp.add_handler(conv_handler)

    dp.add_handler(MessageHandler(Filters.text, store_phrase_handler))

    dp.add_handler(InlineQueryHandler(inline_query))

    dp.add_error_handler(error)

    updater.start_polling()

    upgrade_thread = StampUpgradeThread(bot_data, upgrade_thread_stop_event, updater)
    upgrade_thread.start()

    updater.idle()


if __name__ == '__main__':
    main()
