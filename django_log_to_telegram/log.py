import io
import logging
import traceback
import time

import requests

from .telegram import QueueBot
from telegram import ParseMode
from telegram.error import RetryAfter, TimedOut

class TelegramFormatter(logging.Formatter):
    """
    an extension of the usual logging.Formatter to simplify transmitted data
    """
    meta_attrs = [
        'REMOTE_ADDR',
        'HOSTNAME',
        'HTTP_REFERER'
    ]
    limit = -1  # default per logging.Formatter is None

    def format(self, record):
        """
        same as logging.Formatter.format, with added reporting of the meta_attrs when found in request.META, and the
        username that generated the Exception
        """
        s = super().format(record)

        s += "\n{attr}: {value}".format(
            attr='USER',
            value=record.request.user
        )
        for attr in self.meta_attrs:
            if attr in record.request.META:
                s += "\n{attr}: {value}".format(
                    attr=attr,
                    value=record.request.META[attr]
                )
        return s

    def formatException(self, ei):
        """
        same as logging.Formatter.formatException except for the limit passed as a variable
        """
        sio = io.StringIO()
        tb = ei[2]

        traceback.print_exception(ei[0], ei[1], tb, self.limit, sio)
        s = sio.getvalue()
        print(s)
        sio.close()
        if s[-1:] == "\n":
            s = s[:-1]
        
        print("==================")
        print(s)
        return s


class AdminTelegramHandler(logging.Handler):
    """An exception log handler that send a short log to a telegram bot.

    """

    def __init__(self, *args, **kwargs):
        super().__init__()

        ''''''
        if 'bot_token' in kwargs:
            self.bot_token = kwargs['bot_token']
        elif 'bot_id' in kwargs:
            self.bot_token = kwargs['bot_id']

        self.bot_data = None

        self.setFormatter(TelegramFormatter())

    def emit(self, record):
        if not self.bot_data:
            from django_log_to_telegram.models import BotData
            self.bot_data, created = BotData.objects.get_or_create(
                bot_token=self.bot_token
            )

            if created:
                self.bot_data.get_chat_id()
        self.send_message(self.format(record))

    def prepare_json_for_answer(self, data):
        if not self.bot_data.chat_id:
            self.bot_data.get_chat_id()
        if self.bot_data.chat_id:
            json_data = {
                "chat_id": self.bot_data.chat_id,
                "text": data,
                "parse_mode": 'HTML',
            }

            return json_data
        else:
            return {}

    def send_message(self, message):
        bot = QueueBot(token=self.bot_data.bot_token)
        if not self.bot_data.chat_id:
            self.bot_data.get_chat_id()

        try:
            bot.sendMessage(
                chat_id=self.bot_data.chat_id,
                text=message,
                parse_mode=ParseMode.HTML
            )
        except RetryAfter as e:
            time.sleep(e.retry_after)
            bot.sendMessage(
                chat_id=self.bot_data.chat_id,
                text=message,
                parse_mode=ParseMode.HTML
            )
        except TimedOut:
            time.sleep(5)
            bot.sendMessage(
                chat_id=self.bot_data.chat_id,
                text=message,
                parse_mode=ParseMode.HTML
            )
