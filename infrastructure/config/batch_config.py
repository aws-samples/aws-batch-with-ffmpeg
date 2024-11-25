from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecs as ecs

PROCESSOR_CONFIGS = {
    "nvidia": {
        "instance_classes": [ec2.InstanceClass.G4DN],
        "additional_instances": [ec2.InstanceClass.G5],
        "excluded_regions": ["eu-west-3"],
        "container_tag": "6.0-nvidia2004-amd64",
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
    # https://github.com/Xilinx/video-sdk/issues/97
    # "xilinx": {
    #     "instance_types": [
    #         ec2.InstanceType.of(ec2.InstanceClass.VT1, ec2.InstanceSize.XLARGE3)
    #     ],
    #     "container_tag": "4.4-xilinx2004-amd64",
    #     "ami_ssm_parameter": "/aws/service/marketplace/prod-sw4gdej5auini/3.0.0",
    #     "gpu": None,
    #     "container_type": "EC2",
    #     "spot": True,
    #     "linux_parameters": {
    #         "devices": [
    #             {
    #                 "container_path": "/sys/bus/pci/devices",
    #                 "host_path": "/sys/bus/pci/devices",
    #                 "permissions": [
    #                     batch.DevicePermission.READ,
    #                     batch.DevicePermission.WRITE,
    #                 ],
    #             },
    #             {
    #                 "container_path": "/dev/dri",
    #                 "host_path": "/dev/dri",
    #                 "permissions": [
    #                     batch.DevicePermission.READ,
    #                     batch.DevicePermission.WRITE,
    #                 ],
    #             },
    #         ],
    #     },
    #     "environment": {"XILINX_VISIBLE_DEVICES": "0,1"},
    #     "privileged": True,
    # },
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

# FSx Lustre configurations
LUSTRE_MOUNT_POINT = "/fsx-lustre"

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
