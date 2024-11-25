import logging
import os
import time
import boto3

LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
logging.basicConfig(level=LOGLEVEL)

logging.info("Deleting all Network Interfaces")

ec2 = boto3.client("ec2")
fsx = boto3.client("fsx")

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

# First, delete any FSx for Lustre file systems
try:
    fsx_response = fsx.describe_file_systems()
    for fs in fsx_response.get("FileSystems", []):
        if any(
            tag.get("Key") == tag_key and tag.get("Value") == tag_value
            for tag in fs.get("Tags", [])
        ):
            fs_id = fs["FileSystemId"]
            logging.info(f"Found FSx file system: {fs_id}")
            try:
                fsx.delete_file_system(FileSystemId=fs_id)
                logging.info(f"Initiated deletion of FSx file system: {fs_id}")

                # Wait for the file system to be deleted
                while True:
                    try:
                        fsx.describe_file_systems(FileSystemIds=[fs_id])
                        logging.info(
                            f"Waiting for FSx file system {fs_id} to be deleted..."
                        )
                        time.sleep(30)
                    except fsx.exceptions.FileSystemNotFound:
                        logging.info(f"FSx file system {fs_id} has been deleted")
                        break
            except Exception as e:
                logging.error(f"Error deleting FSx file system {fs_id}: {e}")
except Exception as e:
    logging.error(f"Error describing FSx file systems: {e}")

# Now handle the network interfaces
response = ec2.describe_network_interfaces(
    Filters=[
        {"Name": "vpc-id", "Values": [vpc_id]},
        {"Name": "interface-type", "Values": ["interface"]},
    ]
)

# Loop through the network interfaces and detach them first
for interface in response["NetworkInterfaces"]:
    interface_id = interface["NetworkInterfaceId"]

    # Skip if this is a primary network interface (device index 0)
    if "Attachment" in interface and interface["Attachment"].get("DeviceIndex") == 0:
        logging.info(f"Skipping primary network interface {interface_id}")
        continue

    # Skip if the interface is already available
    if interface.get("Status") == "available":
        try:
            ec2.delete_network_interface(NetworkInterfaceId=interface_id)
            logging.info(f"Deleted available network interface: {interface_id}")
            continue
        except Exception as e:
            logging.error(
                f"Error deleting available network interface {interface_id}: {e}"
            )
            continue

    # For attached interfaces, try to detach first
    if "Attachment" in interface:
        attachment_id = interface["Attachment"]["AttachmentId"]
        try:
            ec2.detach_network_interface(AttachmentId=attachment_id, Force=True)
            logging.info(f"Detached network interface: {interface_id}")

            # Wait until the network interface status is 'available'
            retry_count = 0
            max_retries = 12  # 1 minute total wait time
            while retry_count < max_retries:
                try:
                    eni_response = ec2.describe_network_interfaces(
                        NetworkInterfaceIds=[interface_id]
                    )
                    if eni_response["NetworkInterfaces"][0]["Status"] == "available":
                        logging.info(f"Network interface {interface_id} is available")
                        break
                except Exception as e:
                    logging.warning(f"Error checking interface status: {e}")
                    break

                time.sleep(5)
                retry_count += 1
                logging.info(
                    f"Waiting for network interface {interface_id} to become available..."
                )

            # Try to delete the interface
            if retry_count < max_retries:
                try:
                    ec2.delete_network_interface(NetworkInterfaceId=interface_id)
                    logging.info(f"Deleted network interface: {interface_id}")
                except Exception as e:
                    logging.error(
                        f"Error deleting network interface {interface_id}: {e}"
                    )
        except Exception as e:
            logging.error(
                f"Error detaching network interface {interface_id} with attachment {attachment_id}: {e}"
            )

logging.info("Network interface cleanup completed")
