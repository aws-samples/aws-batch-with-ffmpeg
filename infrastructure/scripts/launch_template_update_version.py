import logging
import os

import boto3

LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
logging.basicConfig(level=LOGLEVEL)


def update_launch_templates():
    # Get the latest launch template version
    ec2 = boto3.client("ec2")

    # Get the launch templates
    response = ec2.describe_launch_templates(
        Filters=[{"Name": "tag:application", "Values": ["batch-ffmpeg"]}]
    )
    launch_templates = response["LaunchTemplates"]

    # Print the launch templates
    for launch_template in launch_templates:
        latest_version = launch_template["LatestVersionNumber"]
        launch_template_id = launch_template["LaunchTemplateId"]
        launch_template_name = launch_template["LaunchTemplateName"]
        # Update the default version
        ec2.modify_launch_template(
            LaunchTemplateId=launch_template_id, DefaultVersion=str(latest_version)
        )
        logging.info(
            "Updated launch template %s to version %s",
            launch_template_name,
            latest_version,
        )


update_launch_templates()
