import asyncio
import logging
import re
import time
from typing import Any, Optional

import httpx
import telegram
from telegram import Update
from telegram.request import HTTPXRequest

from example.configuration.storage_keys import SKeys
from smarthouse.storage import Storage
from smarthouse.utils import Singleton

logger = logging.getLogger("root")


class TGException(Exception):
    pass


async def unknown_handler(tg_client: "TGClient", update: Update):
    if update.message is None:
        return
    await tg_client.write_tg(
        "Sorry, I didn't understand that command",
        replay_message_id=update.message.id,
        to_delete=True,
        to_delete_timestamp=time.time() + 5,
    )


class TGClient(metaclass=Singleton):
    _chat_id: str
    _bot: telegram.Bot
    _r_lock = asyncio.Lock()
    _w_lock = asyncio.Lock()
    _prod: bool
    to_delete_messages: asyncio.PriorityQueue
    handlers: dict
    default_handler: Any
    telegram_token: str | None

    def init(self, telegram_token: str | None = None, telegram_chat_id: str = "", prod: bool = False) -> None:
        self._chat_id = telegram_chat_id
        self._r_lock = asyncio.Lock()
        self._w_lock = asyncio.Lock()
        self._prod = prod
        self.to_delete_messages: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.handlers: dict = {}
        self.default_handler = unknown_handler
        self.telegram_token = telegram_token
        if telegram_token is None:
            return
        self._bot: telegram.Bot = telegram.Bot(
            telegram_token,
            get_updates_request=HTTPXRequest(
                connection_pool_size=10, read_timeout=5, write_timeout=1, connect_timeout=1, pool_timeout=1
            ),
            request=HTTPXRequest(
                connection_pool_size=10, read_timeout=5, write_timeout=5, connect_timeout=1, pool_timeout=1
            ),
        )

    def register_handler(self, pattern, func):
        self.handlers[re.compile(pattern)] = func

    def get_handler(self, message: str):
        for pattern, handler in self.handlers.items():
            try:
                if pattern.match(message):
                    return handler
            except Exception as exc:
                logger.exception(exc)
        return self.default_handler

    async def write_tg(
        self, message: str, replay_message_id=None, to_delete: bool = False, to_delete_timestamp: float = 0
    ):
        if not self._prod or self.telegram_token is None:
            return
        if len(message) == 0:
            return
        message = message.rstrip("\n").strip()
        _exc: Optional[Exception] = None
        response_message_id = None
        done = False
        for _ in range(40):
            async with self._w_lock:
                try:
                    async with self._bot:
                        response = await self._bot.send_message(
                            text=message,
                            chat_id=self._chat_id,
                            disable_notification=True,
                            reply_to_message_id=replay_message_id,
                        )
                        response_message_id = response.message_id
                        done = True
                        break
                except (telegram.error.NetworkError, telegram.error.TimedOut) as exc:
                    _exc = exc
                except httpx.ReadError as exc:
                    _exc = exc
                except telegram.error.BadRequest as exc:
                    if exc.message == "Message is too long":
                        sep = len(message) // 2
                        new_lines = [m.end() for m in re.finditer("\n", message)]
                        if new_lines:
                            old_line = 0
                            cur_line = 0
                            for new_line in new_lines:
                                old_line = cur_line
                                cur_line = new_line
                                if cur_line >= len(message) / 2:
                                    break

                            if cur_line - len(message) / 2 > len(message) / 2 - old_line:
                                sep = old_line
                            else:
                                sep = cur_line

                        await self.write_tg(
                            message[:sep],
                            replay_message_id=replay_message_id,
                            to_delete=to_delete,
                            to_delete_timestamp=to_delete_timestamp,
                        )
                        await self.write_tg(
                            message[sep:],
                            replay_message_id=replay_message_id,
                            to_delete=to_delete,
                            to_delete_timestamp=to_delete_timestamp,
                        )
                        done = True
                        break
                    elif exc.message == "Message text is empty":
                        _exc = exc
                        break
                    else:
                        _exc = exc
                except Exception as exc:
                    _exc = exc

            await asyncio.sleep(0.1)

        if _exc is not None:
            raise _exc
        if not done:
            raise TGException("unknown")

        if to_delete:
            if replay_message_id is not None:
                await self.to_delete_messages.put((to_delete_timestamp, replay_message_id))
            if response_message_id is not None:
                await self.to_delete_messages.put((to_delete_timestamp, response_message_id))

    async def write_tg_document(self, document):
        if not self._prod or self.telegram_token is None:
            return

        _exc = None
        for _ in range(20):
            async with self._w_lock:
                try:
                    async with self._bot:
                        await self._bot.send_document(
                            chat_id=self._chat_id,
                            document=document,
                            disable_notification=True,
                            write_timeout=40,
                        )
                        return
                except (telegram.error.NetworkError, telegram.error.TimedOut) as exc:
                    _exc = exc
                except (httpx.ReadError, telegram.error.BadRequest) as exc:
                    _exc = exc
                except Exception as exc:
                    _exc = exc

            await asyncio.sleep(0.2)

        if _exc is not None:
            raise _exc
        raise TGException("unknown")

    async def delete_message(self, message_id=None):
        if not self._prod or self.telegram_token is None:
            return

        _exc = None
        for _ in range(20):
            async with self._w_lock:
                try:
                    async with self._bot:
                        await self._bot.delete_message(chat_id=self._chat_id, message_id=message_id)
                        return
                except (telegram.error.NetworkError, telegram.error.TimedOut) as exc:
                    _exc = exc
                except telegram.error.BadRequest as exc:
                    if exc.message == "Message to delete not found":
                        return
                    else:
                        _exc = exc
                except httpx.ReadError as exc:
                    _exc = exc
                except Exception as exc:
                    _exc = exc

            await asyncio.sleep(0.2)

        if _exc is not None:
            raise _exc
        raise TGException("unknown")

    async def update_tg(self):
        if not self._prod or self.telegram_token is None:
            return
        storage = Storage()
        updates = []
        async with self._r_lock:
            try:
                async with self._bot:
                    updates = await self._bot.get_updates(
                        offset=storage.get(SKeys.offset_tg), timeout=10, read_timeout=10
                    )
            except (telegram.error.NetworkError, telegram.error.TimedOut):
                pass
            except (httpx.ReadError, telegram.error.BadRequest) as exc:
                raise exc
            except Exception as exc:
                raise exc

        for update in updates:
            storage.put(SKeys.offset_tg, update.update_id + 1)
            if str(update.message.chat_id) == self._chat_id:
                message = update.message.text
                await self.get_handler(message)(self, update)
