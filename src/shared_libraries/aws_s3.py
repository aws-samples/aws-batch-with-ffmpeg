# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
from urllib.parse import urlparse, urlunparse
import logging
import os
from aws_xray_sdk.core import xray_recorder
from botocore.exceptions import ClientError
from typing import List
import boto3

LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
logging.basicConfig(level=LOGLEVEL)
logger = logging.getLogger(__name__)
logging.getLogger("aws_xray_sdk").setLevel(LOGLEVEL)


class S3Url:
    """A class for parsing and representing S3 URLs.

    Examples:
        >>> s = S3Url("s3://bucket/hello/world")
        >>> s.bucket
        'bucket'
        >>> s.key
        'hello/world'
        >>> s.url
        's3://bucket/hello/world'

        >>> s = S3Url("s3://bucket/hello/world?qwe1=3#ddd")
        >>> s.key
        'hello/world?qwe1=3#ddd'
        >>> s.url
        's3://bucket/hello/world?qwe1=3#ddd'

        >>> s = S3Url("s3://bucket/hello/world#foo?bar=2")
        >>> s.key
        'hello/world#foo?bar=2'
        >>> s.url
        's3://bucket/hello/world#foo?bar=2'
    """

    def __init__(self, url: str):
        self._parsed = urlparse(url, allow_fragments=False)

    @property
    def bucket(self) -> str:
        """Returns the bucket name from the S3 URL."""
        return self._parsed.netloc

    @property
    def key(self) -> str:
        """Returns the key (object path) from the S3 URL, including query and
        fragment."""
        path = self._parsed.path.lstrip("/")
        query = f"?{self._parsed.query}" if self._parsed.query else ""
        fragment = f"#{self._parsed.fragment}" if self._parsed.fragment else ""
        return f"{path}{query}{fragment}"

    @property
    def url(self) -> str:
        """Returns the original S3 URL."""
        return urlunparse(self._parsed)


@xray_recorder.capture("download")
def download_s3_files(s3_client, s3_urls: List[str], destination_dir: str) -> List[str]:
    """Download files from S3 to a local directory.

    Args:
        s3_client: The boto3 S3 client.
        s3_urls (list): A list of S3 URLs to download.
        destination_dir (str): The local directory to download the files to.

    Returns:
        list: A list of local file paths for the downloaded files.
    """
    files = []
    for s3_url in s3_urls:
        parse = S3Url(s3_url)
        path_file = os.path.join(destination_dir, parse.key)
        os.makedirs(os.path.dirname(path_file), exist_ok=True)
        logging.info(
            f"Downloading S3 object from (bucket:{parse.bucket} - key:{parse.key}) to {path_file}"
        )
        s3_client.download_file(parse.bucket, parse.key, path_file)
        files.append(path_file)
    return files


@xray_recorder.capture("upload")
def upload_file_to_s3(s3_client, file: str, s3_bucket: str, s3_key: str):
    """Upload a file to S3, checking if it already exists first.

    Args:
        s3_client: The boto3 S3 client.
        file (str): The local path of the file to upload.
        s3_bucket (str): The name of the S3 bucket to upload to.
        s3_key (str): The S3 key (path) to upload the file to.
    """
    logging.info(f'Searching "{s3_key}" in "{s3_bucket}"')
    try:
        s3_client.head_object(Bucket=s3_bucket, Key=s3_key)
        logging.info(f"Path found on S3! Skipping {s3_key}...")
    except ClientError:
        logging.info(f"Uploading {file} in {s3_key}")
        s3_client.upload_file(file, s3_bucket, s3_key)


@xray_recorder.capture("upload")
def sync_dir_to_s3(s3_client, source_dir: str, s3_bucket: str, s3_key: str):
    """Synchronize a local directory to an S3 bucket.

    Args:
        s3_client: The boto3 S3 client.
        source_dir (str): The local directory to sync.
        s3_bucket (str): The name of the S3 bucket to sync to.
        s3_key (str): The S3 key (path) to sync the directory to.
    """
    logging.info(f"Sync of {source_dir} to {s3_bucket} - {s3_key}")
    for root, _, files in os.walk(source_dir):
        for filename in files:
            local_path = os.path.join(root, filename)
            relative_path = os.path.relpath(local_path, source_dir)
            s3_path = os.path.join(s3_key, relative_path)
            upload_file_to_s3(s3_client, local_path, s3_bucket, s3_path)


def s3_key_exists(s3_client, bucket: str, key: str) -> bool:
    s3_client = boto3.client("s3")
    try:
        s3_client.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            logger.info(f"Object ({bucket}/{key}) does not exist on S3.")
            return False
        else:
            logger.error(f"Error checking S3 object ({bucket}/{key}): {e}")
            raise
