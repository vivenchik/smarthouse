import asyncio
import functools
import json
import logging
import time
from typing import Optional

import aioboto3
import aiohttp
import jwt

from smarthouse.utils import Singleton

logger = logging.getLogger("root")


def retry(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        _exc = Exception()
        for _ in range(10):
            try:
                return await func(*args, **kwargs)
            except Exception as exc:
                logger.exception(exc)
                _exc = exc

            await asyncio.sleep(0.1)

        raise _exc

    return wrapper


class YandexCloudException(Exception):
    pass


class YandexCloudClient(metaclass=Singleton):
    service_account_id: str
    key_id: str
    private_key: str
    iam_token: str
    iam_refreshed: int
    iam_client: aiohttp.ClientSession

    async def init(
        self,
        service_account_id: str,
        key_id: str,
        private_key: str,
        aws_access_key_id: str,
        aws_secret_access_key: str,
        s3_mode: bool = True,
        iam_mode: bool = True,
    ):
        self.s3_mode = s3_mode
        self.iam_mode = iam_mode

        self.service_account_id = service_account_id
        self.key_id = key_id
        self.private_key = private_key

        self.endpoint_url = "https://storage.yandexcloud.net"
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key

        self.iam_token = ""
        self.iam_refreshed = 0

        if self.iam_mode:
            self.iam_client = aiohttp.ClientSession(
                base_url="https://iam.api.cloud.yandex.net",
                headers={"Content-Type": "application/json"},
                connector=aiohttp.TCPConnector(
                    ssl=False,
                    limit=None,  # type: ignore[arg-type]
                    force_close=True,
                    enable_cleanup_closed=True,
                ),
                timeout=aiohttp.ClientTimeout(total=3),
            )

        if self.s3_mode:
            self.boto_session = aioboto3.session.Session(
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                region_name="ru-central1",
            )

    @retry
    async def get_bucket(self, bucket: str, key: str) -> bytes:
        async with self.boto_session.client(service_name="s3", endpoint_url=self.endpoint_url) as s3:
            s3_ob = await s3.get_object(Bucket=bucket, Key=key)

        return await s3_ob["Body"].read()

    @retry
    async def put_bucket(self, bucket: str, key: str, body: str):
        async with self.boto_session.client(service_name="s3", endpoint_url=self.endpoint_url) as s3:
            await s3.put_object(Bucket=bucket, Key=key, Body=body)

    @retry
    async def iam_request(self, method: str, path: str, data: Optional[dict] = None) -> dict:
        async with self.iam_client.request(method, path, data=json.dumps(data)) as response:
            response.raise_for_status()
            return await response.json()

    def get_jwt(self):
        now = int(time.time())
        payload = {
            "aud": "https://iam.api.cloud.yandex.net/iam/v1/tokens",
            "iss": self.service_account_id,
            "iat": now,
            "exp": now + 360,
        }

        encoded_token = jwt.encode(payload, self.private_key, algorithm="PS256", headers={"kid": self.key_id})

        return encoded_token

    async def get_iam_token(self):
        jwt = self.get_jwt()
        response = await self.iam_request("POST", "/iam/v1/tokens", {"jwt": jwt})
        return response["iamToken"]

    async def update_iam_token(self):
        self.iam_token = await self.get_iam_token()
        self.iam_refreshed = int(time.time())
