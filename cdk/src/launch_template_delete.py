import logging
import os

import boto3

LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
logging.basicConfig(level=LOGLEVEL)


def delete_launch_templates():
    ec2 = boto3.client("ec2")
    response = ec2.describe_launch_templates()
    for template in response["LaunchTemplates"]:
        ec2.delete_launch_template(LaunchTemplateId=template["LaunchTemplateId"])
        logging.info("Deleted Launch Template %s", template["LaunchTemplateId"])
    return response


delete_launch_templates()
