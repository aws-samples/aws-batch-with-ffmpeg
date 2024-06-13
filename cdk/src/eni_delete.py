import logging
import os
import time
import boto3

LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
logging.basicConfig(level=LOGLEVEL)

logging.info("Deleting all Network Interfaces")

ec2 = boto3.client("ec2")

tag_key = "application"
tag_value = "batch-ffmpeg"

# Use the DescribeVpcs API to get the VPC details
response = ec2.describe_vpcs(
    Filters=[{"Name": f"tag:{tag_key}", "Values": [tag_value]}]
)
if len(response["Vpcs"]) == 0:
    logging.warning(f"No VPCs found with tag {tag_key}={tag_value}")
    exit(0)
vpc_id = response["Vpcs"][0]["VpcId"]
logging.info(f"Found VPC {vpc_id}")

# Describe the network interfaces
response = ec2.describe_network_interfaces(
    Filters=[
        {"Name": "vpc-id", "Values": [vpc_id]},
        {"Name": "interface-type", "Values": ["interface"]},
    ]
)
# Loop through the network interfaces and detach them first
for interface in response["NetworkInterfaces"]:
    interface_id = interface["NetworkInterfaceId"]
    attachment_id = interface["Attachment"]["AttachmentId"]
    try:
        # Detach the network interface
        ec2.detach_network_interface(AttachmentId=attachment_id, Force=True)
        logging.info(f"Detached network interface: {interface_id}")
    except Exception as e:
        logging.info(
            f"Error detaching network interface {interface_id} with attachment {attachment_id}: {e}"
        )

    # Wait until the network interface status is 'available'
    while True:
        eni_response = ec2.describe_network_interfaces(
            NetworkInterfaceIds=[interface_id]
        )
        if eni_response["NetworkInterfaces"][0]["Status"] == "available":
            logging.info(f"Network interface {interface_id} is available...")
            break
        time.sleep(5)
        logging.info(
            f"Waiting for network interface {interface_id} to become available..."
        )

        # Delete the network interface
    try:
        ec2.delete_network_interface(NetworkInterfaceId=interface_id)
        logging.info(f"Deleted network interface: {interface_id}")
    except Exception as e:
        logging.info(f"Error deleting network interface {interface_id}: {e}")
