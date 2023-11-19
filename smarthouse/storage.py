import asyncio
from enum import Enum
from typing import Union

import aiofiles
import yaml

from smarthouse.utils import Singleton


class StorageError(Exception):
    pass


class Storage(metaclass=Singleton):
    _storage: dict
    _storage_shadow: dict
    _storage_name: str | None

    messages_queue: asyncio.Queue
    tasks: asyncio.Queue
    need_to_write: bool

    async def init(self, storage_name: str | None, s3_mode=False):
        self._storage = {}
        self._storage_shadow = {}
        self._storage_name = storage_name
        self._s3_mode = s3_mode
        if s3_mode:
            from smarthouse.yandex_cloud import YandexCloudClient

            self.cloud_client = YandexCloudClient()
        self._lock = asyncio.Lock()

        self.messages_queue = asyncio.Queue()
        self.tasks = asyncio.Queue()
        self.need_to_write = False

        if self._storage_name is not None:
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
        for _ in range(10):
            if not self._s3_mode:
                async with aiofiles.open(f"./storage/{self._storage_name}", mode="r") as f:
                    content = await f.read()
            else:
                content = await self.cloud_client.get_bucket("home-bucket", self._storage_name)

            if (isinstance(content, str) or isinstance(content, bytes)) and content:
                data = yaml.safe_load(content)
                if data:
                    return data

            await asyncio.sleep(0.1)

        raise StorageError("empty data on read")

    async def refresh(self) -> None:
        self._storage = await self._read_storage()

    async def _write_storage(self, force=False):
        if self._storage_name is None:
            return
        if not self._storage:
            raise StorageError("empty data on write")
        async with self._lock:
            if self.need_to_write or force:
                if not self._s3_mode:
                    async with aiofiles.open(f"./storage/{self._storage_name}", mode="w") as f:
                        await f.write(yaml.dump(self._storage))
                else:
                    await self.cloud_client.put_bucket("home-bucket", "storage.yaml", yaml.dump(self._storage))
                self.need_to_write = False

    def put(self, key: Union[Enum, str], value, shadow: bool = False):
        _key: str = key.value if isinstance(key, Enum) else key
        if not shadow:
            if self._storage.get(_key) != value:
                self._storage[_key] = value
                self.need_to_write = True
        else:
            self._storage_shadow[_key] = value

    def write_shadow(self):
        for _key, value in self._storage_shadow.items():
            self.put(_key, value)

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
