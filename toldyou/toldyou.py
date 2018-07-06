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

DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'


class RecordType(Enum):
    PHRASE = 1


logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.DEBUG)
logger = logging.getLogger(__name__)

bot_data = db.get_bot_data()


def store_phrase(user_id, phrase):
    timestamp = certify.generate(bytes(phrase, 'UTF-8'))
    record = {'user': user_id,
              'created': dt.datetime.utcnow(),
              'text': phrase,
              'type': RecordType.PHRASE,
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
    store_phrase(user_id, update.message.text)
    update.message.reply_text('Got it!')
    return ConversationHandler.END


def list_command(bot, update):
    user_id = update.message.from_user.id
    users_records = get_users_stored_records(user_id)

    if users_records.count() == 0:
        update.message.reply_text('Nothing is stored yet!')

    else:
        update.message.reply_text('Here we go:')
        for item in users_records:
            text = '_{}:_\n{}'.format(item['created'].strftime(DATETIME_FORMAT),
                                      item['text'])
            update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


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
