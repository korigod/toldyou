# Told You!

Told You is a Telegram bot that stores an information (string), timestamping it
on the Bitcoin blockchain so you can prove in future that you knew something at
some date. This proof is cryptographically secure and in some cases can be used
even in a court.

To timestamp a large document you can calculate it's hash and send it to the bot.

The bot username in Telegram is [@ToldYouBot](https://t.me/ToldYouBot).

First, send the phrase or hash you want to timestamp to the bot, using `/store`
command. Then you can use the bot in the inline mode to prove someone that you
really obtained this information at the specific date and time: just type
`@ToldYouBot` in any conversation and choose the phrase you want to show. The
phrase will be sent to this chat with a link to a blockchain proof (hash tree).
Please keep in mind that the blockchain verification takes some time, usually
from half an hour to an hour or two.

Please note that this is the early alpha version provided with no guarantees.
