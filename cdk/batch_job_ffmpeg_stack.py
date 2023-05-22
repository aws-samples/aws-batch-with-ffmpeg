# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
import copy
import os

import aws_cdk as cdk
import boto3
from aws_cdk import Stack
from aws_cdk import aws_batch_alpha as batch
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from constructs import Construct

from cdk.constructs.video_batch_job import VideoBatchJob
from cdk.registry_stack import RegistryStack


def concatenate_seq(sequences):
    iterable = iter(sequences)
    head = next(iterable)
    concatenated_sequence = copy.copy(head)
    for sequence in iterable:
        concatenated_sequence += sequence
    return concatenated_sequence


class BatchJobFfmpegStack(Stack):
    """Main stack with AWS Batch."""

    # AWS Batch Jobs
    video_batch_jobs = []
    _region = os.environ.get("CDK_DEPLOY_REGION", os.environ["CDK_DEFAULT_REGION"])

    def _get_instance_types_available(
        self,
        instance_families: list,
        instance_sizes: list = [
            ec2.InstanceSize.LARGE,
            ec2.InstanceSize.XLARGE,
            ec2.InstanceSize.XLARGE2,
        ],
    ):
        """instance_families : List of instance families wanted
        return the list of instance types wanted available in the current region
        """

        # Get all instances wanted
        client = boto3.client("ec2")
        instance_types_wanted_str = []
        result = []
        for instance_family in instance_families:
            for instance_size in instance_sizes:
                instance_type = ec2.InstanceType.of(instance_family, instance_size)
                instance_types_wanted_str.append(instance_type.to_string())

        # Get all instances available in the region
        response = client.describe_instance_type_offerings(
            LocationType="region",
            Filters=[
                {
                    "Name": "location",
                    "Values": [
                        self._region,
                    ],
                },
            ],
        )
        instance_types_available_str = []
        for instance_type_offerings in response["InstanceTypeOfferings"]:
            instance_types_available_str.append(instance_type_offerings["InstanceType"])

        # Get instances wanted available in the region
        result_str = list(
            set(instance_types_available_str).intersection(
                set(instance_types_wanted_str)
            )
        )
        result = list(map(lambda x: ec2.InstanceType(x), result_str))
        return result

    def __init__(
        self, scope: Construct, construct_id: str, ecr_registry: RegistryStack, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # VPC
        vpc = ec2.Vpc(
            self,
            id="vpc",
            nat_gateways=0,
            max_azs=99,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="private-isolated-subnet",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                )
            ],
        )
        subnets = ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED)
        sg_batch = ec2.SecurityGroup(
            self,
            id="sg-batch",
            vpc=vpc,
            description="AWS Batch ffmpeg workers",
            security_group_name="aws-batch-ffmpeg-sg-compute-env",
        )

        s3_bucket = s3.Bucket(
            self,
            id="batch-ffmpeg-bucket",
            # public_read_access=False,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            # server_access_logs_prefix="access-logs/",
            enforce_ssl=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
        )
        # VPC Flow Logs
        log_group = logs.LogGroup(self, "flow-logs-group")
        role = iam.Role(
            self,
            "MyCustomRole",
            assumed_by=iam.ServicePrincipal("vpc-flow-logs.amazonaws.com"),
        )
        ec2.FlowLog(
            self,
            "FlowLog",
            resource_type=ec2.FlowLogResourceType.from_vpc(vpc),
            destination=ec2.FlowLogDestination.to_cloud_watch_logs(log_group, role),
        )

        # VPC Endpoints
        vpc.add_gateway_endpoint(
            "vpce-s3", service=ec2.GatewayVpcEndpointAwsService.S3, subnets=[subnets]
        )
        vpc.add_interface_endpoint(
            "vpce-ecr", service=ec2.InterfaceVpcEndpointAwsService.ECR, subnets=subnets
        )
        vpc.add_interface_endpoint(
            "vpce-ecr-docker",
            service=ec2.InterfaceVpcEndpointAwsService.ECR_DOCKER,
            subnets=subnets,
        )
        vpc.add_interface_endpoint(
            "vpce-cloudwatch-logs",
            service=ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_LOGS,
            subnets=subnets,
        )
        vpc.add_interface_endpoint(
            "vpce-cloudwatch",
            service=ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH,
            subnets=subnets,
        )
        vpc.add_interface_endpoint(
            "vpce-ecs", service=ec2.InterfaceVpcEndpointAwsService.ECS, subnets=subnets
        )
        vpc.add_interface_endpoint(
            "vpce-ecs-agent",
            service=ec2.InterfaceVpcEndpointAwsService.ECS_AGENT,
            subnets=subnets,
        )
        vpc.add_interface_endpoint(
            "vpce-ecs-telemetry",
            service=ec2.InterfaceVpcEndpointAwsService.ECS_TELEMETRY,
            subnets=subnets,
        )
        vpc.add_interface_endpoint(
            "vpce-xray",
            service=ec2.InterfaceVpcEndpointAwsService.XRAY,
            subnets=subnets,
        )
        vpc.add_interface_endpoint(
            "vpce-ssm", service=ec2.InterfaceVpcEndpointAwsService.SSM, subnets=subnets
        )

        # IAM
        batch_instance_role = iam.Role(
            self,
            "batch-job-instance-role",
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("ec2.amazonaws.com"),
                iam.ServicePrincipal("ecs.amazonaws.com"),
                iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            ),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonEC2ContainerServiceforEC2Role"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AWSXrayWriteOnlyAccess"
                ),
            ],
        )
        s3_bucket.grant_read_write(batch_instance_role)

        batch_instance_profile = iam.CfnInstanceProfile(
            self, "instance-profile", roles=[batch_instance_role.role_name]
        )
        batch_instance_profile.node.add_dependency(batch_instance_role)

        account = os.environ.get(
            "CDK_DEPLOY_ACCOUNT", os.environ["CDK_DEFAULT_ACCOUNT"]
        )
        region = os.environ.get("CDK_DEPLOY_REGION", os.environ["CDK_DEFAULT_REGION"])
        batch_job_role = iam.Role(
            self,
            "batch-job-role",
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("ecs.amazonaws.com"),
                iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            ),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonECSTaskExecutionRolePolicy"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AWSXrayWriteOnlyAccess"
                ),
            ],
            inline_policies={
                "get-ssm-parameters": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "ssm:GetParameters",
                                "ssm:GetParameter",
                                "ssm:GetParametersByPath",
                                "secretsmanager:GetSecretValue",
                                "kms:Decrypt",
                            ],
                            resources=[
                                f"arn:aws:ssm:{region}:{account}"
                                f":parameter/batch-ffmpeg/*",
                                f"arn:aws:ssm:{region}:{account}"
                                f":parameter/batch-ffmpeg",
                            ],
                        )
                    ]
                )
            },
        )

        s3_bucket.grant_read_write(batch_job_role)

        batch_execution_role = iam.Role(
            self,
            "batch-execution-role",
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("ecs.amazonaws.com"),
                iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            ),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonECSTaskExecutionRolePolicy"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AWSXrayWriteOnlyAccess"
                ),
            ],
        )

        # AMIs
        ecs_amd64_ami = ec2.MachineImage.from_ssm_parameter(
            "/aws/service/ecs/optimized-ami/amazon-linux-2/recommended/image_id"
        )
        ecs_arm64_ami = ec2.MachineImage.from_ssm_parameter(
            "/aws/service/ecs/optimized-ami/amazon-linux-2/arm64/recommended/image_id"
        )
        ecs_nvidia_ami = ec2.MachineImage.from_ssm_parameter(
            "/aws/service/ecs/optimized-ami/amazon-linux-2/gpu/recommended/image_id"
        )

        # Compute Environments
        batch_compute_nvidia_instancetypes = self._get_instance_types_available(
            [
                ec2.InstanceClass.GRAPHICS4_NVME_DRIVE_HIGH_PERFORMANCE,
                ec2.InstanceClass.GRAPHICS4_AMD_NVME_DRIVE,
            ]
        )

        # Instance types
        batch_compute_intel_instancetypes = self._get_instance_types_available(
            [
                ec2.InstanceClass.COMPUTE5,
                ec2.InstanceClass.COMPUTE5_HIGH_PERFORMANCE,
                ec2.InstanceClass.COMPUTE5_NVME_DRIVE,
                ec2.InstanceClass.COMPUTE6_INTEL,
                ec2.InstanceClass.COMPUTE6_INTEL_HIGH_PERFORMANCE,
                ec2.InstanceClass.COMPUTE6_INTEL_NVME_DRIVE,
                ec2.InstanceClass.STANDARD5,
                ec2.InstanceClass.STANDARD5_HIGH_PERFORMANCE,
                ec2.InstanceClass.STANDARD5_NVME_DRIVE,
                ec2.InstanceClass.STANDARD6_INTEL,
                ec2.InstanceClass.STANDARD6_INTEL_NVME_DRIVE,
            ]
        )

        batch_compute_arm_instancetypes = self._get_instance_types_available(
            [
                ec2.InstanceClass.COMPUTE6_GRAVITON2,
                ec2.InstanceClass.STANDARD6_GRAVITON,
            ]
        )
        if self._region != "ap-southeast-2":
            # Graviton 3 is available in this region but not yet in AWS Batch
            graviton_three = self._get_instance_types_available(
                [
                    ec2.InstanceClass.COMPUTE7_GRAVITON3,
                    ec2.InstanceClass.STANDARD7_GRAVITON,
                ]
            )
            # Concatenate all sequences
            batch_compute_arm_instancetypes = [
                *batch_compute_arm_instancetypes,
                *graviton_three,
            ]

        batch_compute_amd_instancetypes = self._get_instance_types_available(
            [
                ec2.InstanceClass.COMPUTE5_AMD,
                ec2.InstanceClass.COMPUTE5_AMD_NVME_DRIVE,
                ec2.InstanceClass.COMPUTE6_AMD,
                ec2.InstanceClass.STANDARD5_AMD,
                ec2.InstanceClass.STANDARD5_AMD_NVME_DRIVE,
            ]
        )
        batch_compute_xilinx_instancetypes = self._get_instance_types_available(
            [
                ec2.InstanceClass.VIDEO_TRANSCODING1,
            ],
            [ec2.InstanceSize.XLARGE3],
        )

        ffmpeg_python_script_command = [
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
        ffmpeg_python_script_default_values = {
            "global_options": "null",
            "input_file_options": "null",
            "input_url": "null",
            "output_file_options": "null",
            "output_url": "null",
            "name": "null",
        }
        job_definition_container_env = {
            "AWS_XRAY_SDK_ENABLED": "true",
            "S3_BUCKET": s3_bucket.bucket_name,
        }

        # Containers
        nvidia_tag = "5.1-nvidia2004-amd64"
        batch_jobdef_nvidia_container = batch.JobDefinitionContainer(
            image=ecs.ContainerImage.from_ecr_repository(ecr_registry, nvidia_tag),
            command=ffmpeg_python_script_command,
            environment=job_definition_container_env,
            job_role=batch_job_role,
            gpu_count=1,
            vcpus=2,
            memory_limit_mib=8192,
        )
        amd64_tag = "5.1-ubuntu2004-amd64"
        batch_jobdef_amd64_container = batch.JobDefinitionContainer(
            image=ecs.ContainerImage.from_ecr_repository(ecr_registry, amd64_tag),
            command=ffmpeg_python_script_command,
            environment=job_definition_container_env,
            job_role=batch_job_role,
            gpu_count=None,
            vcpus=2,
            memory_limit_mib=8192,
        )

        batch_jobdef_fargate_container = batch.JobDefinitionContainer(
            image=ecs.ContainerImage.from_ecr_repository(ecr_registry, amd64_tag),
            command=ffmpeg_python_script_command,
            environment=job_definition_container_env,
            gpu_count=None,
            vcpus=2,
            memory_limit_mib=8192,
            platform_version=ecs.FargatePlatformVersion.LATEST,
            execution_role=batch_execution_role,
            job_role=batch_job_role,
        )

        arm64_tag = "5.1-ubuntu2004-arm64"
        batch_jobdef_arm64_container = batch.JobDefinitionContainer(
            image=ecs.ContainerImage.from_ecr_repository(ecr_registry, arm64_tag),
            command=ffmpeg_python_script_command,
            environment=job_definition_container_env,
            job_role=batch_job_role,
            gpu_count=0,
            vcpus=2,
            memory_limit_mib=8192,
        )

        # AWS Batch job definition, queue, compute Environment
        if batch_compute_nvidia_instancetypes:
            ffmpeg_nvidia_job = VideoBatchJob(
                self,
                construct_id="nvidia-job",
                proc_name="nvidia",
                ec2_ami=ecs_nvidia_ami,
                ec2_vpc=vpc,
                ec2_vpc_sg=sg_batch,
                ec2_vpc_subnets=subnets,
                batch_compute_instancetypes=batch_compute_nvidia_instancetypes,
                batch_jobdef_container=batch_jobdef_nvidia_container,
                batch_jobdef_parameters=ffmpeg_python_script_default_values,
                batch_compute_env_instanceprofile_arn=batch_instance_profile.attr_arn,
            )
            self.video_batch_jobs.append(ffmpeg_nvidia_job)

        if batch_compute_xilinx_instancetypes:
            ffmpeg_xilinx_job = VideoBatchJob(
                self,
                construct_id="xilinx-job",
                proc_name="xilinx",
                ec2_ami=ecs_amd64_ami,
                ec2_vpc=vpc,
                ec2_vpc_sg=sg_batch,
                ec2_vpc_subnets=subnets,
                batch_compute_instancetypes=batch_compute_xilinx_instancetypes,
                batch_jobdef_container=batch_jobdef_amd64_container,
                batch_jobdef_parameters=ffmpeg_python_script_default_values,
                batch_compute_env_instanceprofile_arn=batch_instance_profile.attr_arn,
            )
            self.video_batch_jobs.append(ffmpeg_xilinx_job)

        if batch_compute_intel_instancetypes:
            ffmpeg_intel_job = VideoBatchJob(
                self,
                construct_id="intel-job",
                proc_name="intel",
                ec2_ami=ecs_amd64_ami,
                ec2_vpc=vpc,
                ec2_vpc_sg=sg_batch,
                ec2_vpc_subnets=subnets,
                batch_compute_instancetypes=batch_compute_intel_instancetypes,
                batch_jobdef_container=batch_jobdef_amd64_container,
                batch_jobdef_parameters=ffmpeg_python_script_default_values,
                batch_compute_env_instanceprofile_arn=batch_instance_profile.attr_arn,
            )
            self.video_batch_jobs.append(ffmpeg_intel_job)

        if batch_compute_amd_instancetypes:
            ffmpeg_amd_job = VideoBatchJob(
                self,
                construct_id="amd-job",
                proc_name="amd",
                ec2_ami=ecs_amd64_ami,
                ec2_vpc=vpc,
                ec2_vpc_sg=sg_batch,
                ec2_vpc_subnets=subnets,
                batch_compute_instancetypes=batch_compute_amd_instancetypes,
                batch_jobdef_container=batch_jobdef_amd64_container,
                batch_jobdef_parameters=ffmpeg_python_script_default_values,
                batch_compute_env_instanceprofile_arn=batch_instance_profile.attr_arn,
            )
            self.video_batch_jobs.append(ffmpeg_amd_job)

        if batch_compute_arm_instancetypes:
            ffmpeg_arm_job = VideoBatchJob(
                self,
                construct_id="arm-job",
                proc_name="arm",
                ec2_ami=ecs_arm64_ami,
                ec2_vpc=vpc,
                ec2_vpc_sg=sg_batch,
                ec2_vpc_subnets=subnets,
                batch_compute_instancetypes=batch_compute_arm_instancetypes,
                batch_jobdef_container=batch_jobdef_arm64_container,
                batch_jobdef_parameters=ffmpeg_python_script_default_values,
                batch_compute_env_instanceprofile_arn=batch_instance_profile.attr_arn,
            )
            self.video_batch_jobs.append(ffmpeg_arm_job)

        ffmpeg_fargate_job = VideoBatchJob(
            self,
            construct_id="fargate-job",
            proc_name="fargate",
            ec2_ami=None,
            ec2_vpc=vpc,
            ec2_vpc_sg=sg_batch,
            ec2_vpc_subnets=subnets,
            batch_compute_instancetypes=None,
            batch_jobdef_container=batch_jobdef_fargate_container,
            batch_jobdef_parameters=ffmpeg_python_script_default_values,
            batch_compute_env_instanceprofile_arn=None,
        )
        self.video_batch_jobs.append(ffmpeg_fargate_job)

        self.s3_bucket = s3_bucket

        # Outputs
        cdk.CfnOutput(
            self,
            "S3bucket",
            value=s3_bucket.bucket_name,
            description="S3 Bucket used by the solution to upload/download assets",
        )
