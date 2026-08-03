from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecs as ecs

from src.shared_libraries.s3_posix import POSIX_DIRECTORY_MODE

PROCESSOR_CONFIGS = {
    "nvidia": {
        "instance_classes": [ec2.InstanceClass.G4DN],
        "additional_instances": [ec2.InstanceClass.G5],
        "excluded_regions": ["eu-west-3"],
        "container_tag": "7.0-nvidia2004-amd64",
        "ami_ssm_parameter": "/aws/service/ecs/optimized-ami/amazon-linux-2/gpu/recommended/image_id",
        "gpu": 1,
        "container_type": "EC2",
        "spot": True,
    },
    "intel": {
        "instance_classes": [
            ec2.InstanceClass.C5,
            ec2.InstanceClass.C5N,
            ec2.InstanceClass.C5D,
            ec2.InstanceClass.C6I,
            ec2.InstanceClass.C6IN,
            ec2.InstanceClass.M5,
            ec2.InstanceClass.M5D,
            ec2.InstanceClass.M6I,
            ec2.InstanceClass.M7I,
            ec2.InstanceClass.C7I,
        ],
        "additional_instances": [
            ec2.InstanceClass.M5N,
            ec2.InstanceClass.C6ID,
            ec2.InstanceClass.M6ID,
        ],
        "excluded_regions": ["ap-south-1", "ap-southeast-2", "eu-west-3", "sa-east-1"],
        "container_tag": "7.0-ubuntu2004-amd64",
        "ami_ssm_parameter": "/aws/service/ecs/optimized-ami/amazon-linux-2/recommended/image_id",
        "gpu": None,
        "container_type": "EC2",
        "spot": True,
    },
    "arm": {
        "instance_classes": [
            ec2.InstanceClass.C6G,
            ec2.InstanceClass.C6GD,
            ec2.InstanceClass.C6GN,
            ec2.InstanceClass.M6G,
            ec2.InstanceClass.M7G,
            ec2.InstanceClass.M7GD,
        ],
        "additional_instances": [
            ec2.InstanceClass.M6GD,
            ec2.InstanceClass.C7G,
            ec2.InstanceClass.C7GD,
        ],
        "excluded_regions": [
            "ap-southeast-2",
            "ap-south-1",
            "eu-central-1",
            "sa-east-1",
            "eu-west-3",
        ],
        "container_tag": "7.0-ubuntu2004-arm64",
        "ami_ssm_parameter": "/aws/service/ecs/optimized-ami/amazon-linux-2/arm64/recommended/image_id",
        "gpu": None,
        "container_type": "EC2",
        "spot": True,
    },
    "amd": {
        "instance_classes": [
            ec2.InstanceClass.C5A,
            ec2.InstanceClass.M5A,
            ec2.InstanceClass.M5AD,
        ],
        "additional_instances": [
            ec2.InstanceClass.C5AD,
            ec2.InstanceClass.C6A,
            ec2.InstanceClass.M6A,
            ec2.InstanceClass.C7A,
            ec2.InstanceClass.M7A,
        ],
        "excluded_regions": ["ap-south-1", "eu-west-3", "ap-southeast-2", "sa-east-1"],
        "container_tag": "7.0-ubuntu2004-amd64",
        "ami_ssm_parameter": "/aws/service/ecs/optimized-ami/amazon-linux-2/recommended/image_id",
        "gpu": None,
        "container_type": "EC2",
        "spot": True,
    },
    "fargate": {
        "container_tag": "7.0-ubuntu2004-amd64",
        "container_type": "FARGATE",
        "spot": True,
        "fargate_cpu_architecture": ecs.CpuArchitecture.X86_64,
    },
    "fargate-arm": {
        "container_tag": "7.0-ubuntu2004-arm64",
        "container_type": "FARGATE",
        "spot": False,  # ARM64 doesn't support Fargate Spot as of now
        "fargate_cpu_architecture": ecs.CpuArchitecture.ARM64,
    },
}

# Job definition configurations
JOB_DEF_CPU = 2
JOB_DEF_MEMORY = 8192  # in MiB

# Amazon S3 Files shared file system configuration
S3FILES_MOUNT_POINT = "/mnt/s3files"
# The storage stack publishes the coordinates of the file system under these
# deterministic names, and the hosts that mount it read them at boot. The names
# depend on no resource, which is what keeps the batch stack free of any
# cross-stack import on the file system.
#
# `mount -t s3files -o accesspoint=<access point id> <file system id> <mount
# point>` needs exactly these two values, so exactly these two are published.
S3FILES_FILE_SYSTEM_ID_PARAMETER = "/batch-ffmpeg/s3files/file-system-id"
S3FILES_ACCESS_POINT_ID_PARAMETER = "/batch-ffmpeg/s3files/access-point-id"

# POSIX identity enforced by the access point. The containers run as
# `useradd --uid 1000` / `USER ffmpeg` (src/docker-images/7.0/*/Dockerfile), so
# every file system operation is attributed to that identity.
# tests/unit/test_posix_identity.py asserts the Dockerfiles still agree with
# these two values, which is what keeps the duplication from drifting: a
# Dockerfile cannot read a Python constant.
S3FILES_POSIX_UID = "1000"
S3FILES_POSIX_GID = "1000"

# Value of the `file-permissions` metadata of a directory object. The value is
# declared by src/shared_libraries/s3_posix.py, the module that materializes
# those directories, because that directory is the one the container images
# embed: the containers cannot read the CDK code, so a copy here would be a
# second source of truth for the same file system view.
S3FILES_POSIX_DIRECTORY_MODE = POSIX_DIRECTORY_MODE

# NFS port of the S3 Files mount targets.
S3FILES_NFS_PORT = 2049

# FFMPEG script configurations
FFMPEG_SCRIPT_COMMAND = [
    "--global_options",
    "Ref::global_options",
    "--input_file_options",
    "Ref::input_file_options",
    "--input_url",
    "Ref::input_url",
    "--output_file_options",
    "Ref::output_file_options",
    "--output_url",
    "Ref::output_url",
    "--name",
    "Ref::name",
]

FFMPEG_SCRIPT_DEFAULT_VALUES = {
    "global_options": "null",
    "input_file_options": "null",
    "input_url": "null",
    "output_file_options": "null",
    "output_url": "null",
    "name": "null",
}
