import boto3

from smarthouse.utils import Singleton


class YandexCloudException(Exception):
    pass


class YandexCloudClient(metaclass=Singleton):
    def init(self, aws_access_key_id: str, aws_secret_access_key: str):
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key

        self.boto_session = boto3.session.Session(
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name="ru-central1",
        )
        self.bucket_client = self.boto_session.client(
            service_name="s3", endpoint_url="https://storage.yandexcloud.net"
        )  # todo: async

    async def get_bucket(self, bucket: str, key: str):
        print("get bucket")
        get_object_response = self.bucket_client.get_object(Bucket=bucket, Key=key)
        return get_object_response["Body"].read().decode("utf-8")

    async def put_bucket(self, bucket: str, key: str, body: str):
        print("put bucket")
        self.bucket_client.put_object(Bucket=bucket, Key=key, Body=body)
