import click
import boto3
from botocore.exceptions import ClientError
import logging
import os
import fnmatch
import time

# Set up logging
LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
logging.basicConfig(level=LOGLEVEL)
logger = logging.getLogger(__name__)

# Create an S3 client
s3 = boto3.client("s3")


def delete_bucket_contents(bucket_name):
    """Deletes all objects and versions from the specified bucket.

    :param bucket_name: The name of the bucket to delete the contents
        from.
    """
    try:
        # List all object versions
        paginator = s3.get_paginator("list_object_versions")
        page_iterator = paginator.paginate(Bucket=bucket_name)

        objects_to_delete = []
        logging.info("List objects...")
        page_nb = 0
        for page in page_iterator:
            page_nb = page_nb + 1
            logging.info("Page: %s", str(page_nb))
            versions = page.get("Versions", [])
            delete_markers = page.get("DeleteMarkers", [])

            # Build a list of objects to delete
            for version in versions:
                objects_to_delete.append(
                    {"Key": version["Key"], "VersionId": version["VersionId"]}
                )
            for marker in delete_markers:
                objects_to_delete.append(
                    {"Key": marker["Key"], "VersionId": marker["VersionId"]}
                )

        # Delete the objects in batches of 1000
        while objects_to_delete:
            batch = objects_to_delete[:1000]
            objects_to_delete = objects_to_delete[1000:]
            s3.delete_objects(Bucket=bucket_name, Delete={"Objects": batch})
            logger.info(f"Deleted {len(batch)} objects from {bucket_name}")
    except ClientError as e:
        logger.error(f"Error deleting bucket contents: {e}")


@click.command()
@click.option(
    "--bucket-pattern",
    "-b",
    required=True,
    help="A pattern that can include a wildcard (*) to match multiple bucket names.",
)
def delete_versioned_bucket(bucket_pattern):
    """Deletes all buckets that match the provided pattern, including all
    objects and versions."""
    try:
        # List all buckets
        response = s3.list_buckets()
        buckets = response["Buckets"]

        # Filter buckets that match the pattern
        for bucket in buckets:
            bucket_name = bucket["Name"]
            if fnmatch.fnmatch(bucket_name, bucket_pattern):
                logger.info(f"Deleting bucket: {bucket_name}")
                delete_bucket_contents(bucket_name)
                time.sleep(5)
                s3.delete_bucket(Bucket=bucket_name)
                logger.info(f"Bucket {bucket_name} deleted successfully.")
    except ClientError as e:
        logger.error(f"Error deleting buckets: {e}")


if __name__ == "__main__":
    delete_versioned_bucket()
