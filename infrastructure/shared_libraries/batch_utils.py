# batch_utils.py
"""This module contains utility functions for creating and managing AWS Batch
resources.

It provides functions to get instance classes, container definitions,
and compute environments for different processor types.
"""

from aws_cdk import aws_batch as batch
from aws_cdk import aws_ecs as ecs
import aws_cdk as cdk
from infrastructure.config.batch_config import (
    PROCESSOR_CONFIGS,
    JOB_DEF_CPU,
    JOB_DEF_MEMORY,
    FFMPEG_SCRIPT_COMMAND,
)


def get_instance_classes(proc_name, region):
    """Get the list of instance classes for a given processor type and region.

    Args:
        proc_name (str): The name of the processor type.
        region (str): The AWS region.

    Returns:
        list: A list of EC2 instance classes suitable for the given processor type and region.
    """
    config = PROCESSOR_CONFIGS.get(proc_name, {})
    instance_classes = config.get("instance_classes", [])

    if region not in config.get("excluded_regions", []):
        instance_classes.extend(config.get("additional_instances", []))

    return instance_classes


def get_container_definition(
    self, proc_name, job_definition_container_env, lustre_volumes
):
    """Create a container definition for a given processor type.

    Args:
        self: The CDK construct instance.
        proc_name (str): The name of the processor type.
        job_definition_container_env (dict): Environment variables for the container.
        lustre_volumes (list): List of Lustre volumes to mount.

    Returns:
        Union[batch.EcsFargateContainerDefinition, batch.EcsEc2ContainerDefinition]:
        The created container definition.
    """
    config = PROCESSOR_CONFIGS.get(proc_name, {})

    if "fargate" in proc_name:
        return batch.EcsFargateContainerDefinition(
            self,
            f"container-def-{proc_name}",
            image=ecs.ContainerImage.from_ecr_repository(
                self.ecr_registry, config["container_tag"]
            ),
            command=FFMPEG_SCRIPT_COMMAND,
            environment=job_definition_container_env,
            cpu=config["cpu"],
            memory=cdk.Size.mebibytes(config["memory"]),
            fargate_platform_version=config["fargate_platform_version"],
            execution_role=self.batch_execution_role,
            job_role=self.batch_job_role,
            fargate_cpu_architecture=config.get("fargate_cpu_architecture"),
            volumes=None,
        )
    else:
        container_def_args = {
            "image": ecs.ContainerImage.from_ecr_repository(
                self.ecr_registry, config["container_tag"]
            ),
            "command": FFMPEG_SCRIPT_COMMAND,
            "environment": job_definition_container_env,
            "execution_role": self.batch_execution_role,
            "job_role": self.batch_job_role,
            "gpu": config.get("gpu"),
            "cpu": JOB_DEF_CPU,
            "memory": cdk.Size.mebibytes(JOB_DEF_MEMORY),
            "volumes": lustre_volumes,
        }

        if proc_name == "xilinx":
            linux_parameters = batch.LinuxParameters(self, f"{proc_name}-linux-param")
            for device in config["linux_parameters"]["devices"]:
                linux_parameters.add_device(batch.Device(**device))
            container_def_args["linux_parameters"] = linux_parameters
            container_def_args["privileged"] = config["privileged"]
            container_def_args["environment"].update(config["environment"])

        return batch.EcsEc2ContainerDefinition(
            self, f"container-def-{proc_name}", **container_def_args
        )


def get_compute_environment(self, proc_name):
    """Create a compute environment for a given processor type.

    Args:
        self: The CDK construct instance.
        proc_name (str): The name of the processor type.

    Returns:
        Union[batch.FargateComputeEnvironment, batch.ManagedEc2EcsComputeEnvironment]:
        The created compute environment.
    """
    config = PROCESSOR_CONFIGS.get(proc_name, {})

    if "fargate" in proc_name:
        return batch.FargateComputeEnvironment(
            self,
            f"batch-fargate-compute-environment-{proc_name}",
            vpc=self.vpc,
            security_groups=[self.sg_batch],
            vpc_subnets=self.subnet_selection,
        )
    else:
        return batch.ManagedEc2EcsComputeEnvironment(
            self,
            f"batch-ec2-compute-environment-{proc_name}",
            vpc=self.vpc,
            instance_types=config.get("instance_types"),
            instance_role=self.batch_compute_env_instance_role,
            security_groups=[self.sg_batch],
            vpc_subnets=self.subnet_selection,
            spot=True,
            maxv_cpus=4096,
        )
