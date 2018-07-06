# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, you can obtain one at http://mozilla.org/MPL/2.0/.

import os
import logging
import datetime as dt
from enum import Enum
from uuid import uuid4

from bson.binary import Binary
from telegram import InlineQueryResultArticle, InputTextMessageContent, ParseMode
from telegram.ext import (CommandHandler,
                          InlineQueryHandler,
                          Updater,
                          MessageHandler,
                          Filters,
                          ConversationHandler)
from telegram.utils.helpers import escape_markdown

import db
import certify

DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S UTC'

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.DEBUG)
logger = logging.getLogger(__name__)

bot_data = db.get_bot_data()


def store_phrase(user_id, phrase):
    timestamp = certify.generate(bytes(phrase, 'UTF-8'))
    record = {'user': user_id,
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


def start_command(bot, update):
    update.message.reply_text('Hi! Use /store to store a new prophecy or /list '
                              'to list already made ones. Please note: this is '
                              'an alpha version, your data can be lost.')


def store_command(bot, update):
    update.message.reply_text('Ok, now send me a text to store.')
    return 'STORE_PHRASE'


def store_phrase_handler(bot, update):
    user_id = update.message.from_user.id
    update.message.reply_text('Got it!')
    store_phrase(user_id, update.message.text)
    return ConversationHandler.END


def list_command(bot, update):
    user_id = update.message.from_user.id
    users_records = get_users_stored_records(user_id)

    if users_records.count() == 0:
        update.message.reply_text('Nothing is stored yet!')

    else:
        update.message.reply_text('Here we go:')

        for record in users_records:
            link = None

            if record['blockchained'] is None:
                timestamp = certify.deserialize(record['stamp'])
                if certify.upgrade(timestamp) is True:
                    bot_data.update_one({'_id': record['_id']}, {
                                        '$set': {
                                            'blockchained': dt.datetime.utcnow(),
                                            'stamp': Binary(certify.serialize(timestamp))
                                        }})
                    stamp_hex = certify.serialize(timestamp).hex()
                    link = 'https://opentimestamps.org/info/?{}'.format(stamp_hex)
            else:
                stamp_hex = record['stamp'].hex()
                link = 'https://opentimestamps.org/info/?{}'.format(stamp_hex)

            if link is not None:
                certificate_text = '[Blockchain certificate]({})'.format(link)
            else:
                certificate_text = '_Blockchain verification is pending_'

            text = '_{}:_\n{}\n{}'.format(record['created'].strftime(DATETIME_FORMAT),
                                          record['text'], certificate_text)
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
    # query = update.inline_query.query
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
        text_to_send = '{} told at *{}*:\n{}'.format(user_mention,
                                                     record_created_dt_str,
                                                     record['text'])

        message = InputTextMessageContent(text_to_send,
                                          parse_mode=ParseMode.MARKDOWN)

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
    updater = Updater(os.environ['TELEGRAM_BOT_TOKEN'])
    dp = updater.dispatcher

    dp.add_handler(CommandHandler('start', start_command))
    dp.add_handler(CommandHandler('list', list_command))

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('store', store_command),
                      CommandHandler('delete_all', delete_all_command)],

        states={
            'STORE_PHRASE': [MessageHandler(Filters.text, store_phrase_handler)],
            'DELETE_ALL_RECORDS': [MessageHandler(Filters.text, delete_all_records_handler)]
        },
        fallbacks=[CommandHandler('cancel', cancel_command)]
    )

    dp.add_handler(conv_handler)
    dp.add_handler(InlineQueryHandler(inline_query))
    dp.add_error_handler(error)

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
