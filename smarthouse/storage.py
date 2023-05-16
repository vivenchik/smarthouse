import asyncio
from enum import Enum
from os.path import exists
from typing import Union

import aiofiles
import yaml

from smarthouse.utils import Singleton


class StorageError(Exception):
    pass


class Storage(metaclass=Singleton):
    _storage: dict
    _storage_name: str | None

    messages_queue: asyncio.Queue
    tasks: asyncio.Queue
    need_to_write: bool

    async def init(self, storage_name: str | None):
        self._storage = {}
        self._storage_name = storage_name
        self._lock = asyncio.Lock()

        self.messages_queue = asyncio.Queue()
        self.tasks = asyncio.Queue()
        self.need_to_write = False

        if self._storage_name is not None:
            if not exists(self._storage_name):
                open(self._storage_name, "x")
                self._storage = {}
            else:
                self._storage = await self._read_storage()
        else:
            self._storage = {}
        to_delete = [k for k in self._storage.keys() if k.startswith("__")]
        for k in to_delete:
            self._storage.pop(k)
        await self._write_storage(force=True)

    async def _read_storage(self) -> dict:
        if self._storage_name is None:
            return {}
        data = None
        for _ in range(100):
            async with aiofiles.open(self._storage_name, mode="r") as f:
                content = await f.read()
                data = yaml.safe_load(content)
            if data is not None:
                return data
        raise StorageError("empty data")

    async def refresh(self) -> None:
        self._storage = await self._read_storage()

    async def _write_storage(self, force=False):
        if self._storage_name is None:
            return
        async with self._lock:
            if self.need_to_write or force:
                async with aiofiles.open(self._storage_name, mode="w") as f:
                    await f.write(yaml.dump(self._storage))
                self.need_to_write = False

    def put(self, key: Union[Enum, str], value):
        _key: str = key.value if isinstance(key, Enum) else key
        if self._storage.get(_key) != value:
            self._storage[_key] = value
            self.need_to_write = True

    def delete(self, key: Union[Enum, str]):
        _key: str = key.value if isinstance(key, Enum) else key
        if _key in self._storage.keys():
            self._storage.pop(_key)
            self.need_to_write = True

    def get(self, key: Union[Enum, str], default=0):
        _key: str = key.value if isinstance(key, Enum) else key
        return self._storage.get(_key, default)

    def keys(self):
        return self._storage.keys()

    def items(self):
        return self._storage.items()
