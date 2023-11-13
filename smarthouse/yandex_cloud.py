import aioboto3

from smarthouse.utils import Singleton


class YandexCloudException(Exception):
    pass


class YandexCloudClient(metaclass=Singleton):
    def init(self, aws_access_key_id: str, aws_secret_access_key: str):
        self.endpoint_url = "https://storage.yandexcloud.net"
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key

        self.boto_session = aioboto3.session.Session(
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name="ru-central1",
        )

    async def get_bucket(self, bucket: str, key: str):
        async with self.boto_session.client(service_name="s3", endpoint_url=self.endpoint_url) as s3:
            s3_ob = await s3.get_object(Bucket=bucket, Key=key)

        return await s3_ob["Body"].read()

    async def put_bucket(self, bucket: str, key: str, body: str):
        async with self.boto_session.client(service_name="s3", endpoint_url=self.endpoint_url) as s3:
            await s3.put_object(Bucket=bucket, Key=key, Body=body)
