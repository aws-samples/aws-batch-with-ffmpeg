import logging
import os

import boto3

LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
logging.basicConfig(level=LOGLEVEL)

APPLICATION_NAME = "batch-ffmpeg"

client = boto3.client("servicecatalog-appregistry")
try:
    response = client.list_associated_resources(
        application=APPLICATION_NAME,
    )
    for resource in response["resources"]:
        response = client.disassociate_resource(
            application=APPLICATION_NAME,
            resourceType="CFN_STACK",
            resource=resource["name"],
        )

    response = client.delete_application(application=APPLICATION_NAME)

    logging.info("Delete App Registry Application : %s", str(response))
except client.exceptions.ResourceNotFoundException:
    logging.info(
        "App Registry application already deleted in %s", client.meta.region_name
    )
