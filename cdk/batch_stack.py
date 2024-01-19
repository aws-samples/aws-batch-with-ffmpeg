# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
import copy
import os

import aws_cdk as cdk
from aws_cdk import Stack
from aws_cdk import aws_batch as batch
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_fsx as fsx
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3 as s3
from constructs import Construct

from cdk.constructs.video_batch_job import VideoBatchJob


def concatenate_seq(sequences):
    iterable = iter(sequences)
    head = next(iterable)
    concatenated_sequence = copy.copy(head)
    for sequence in iterable:
        concatenated_sequence += sequence
    return concatenated_sequence


class BatchStack(Stack):
    """Main stack with AWS Batch."""

    # AWS Batch Jobs
    video_batch_jobs = []
    mount_lustre_path = "/fsx-lustre"
    _xilinx_regions = ["us-west-2", "us-east-1", "eu-west-1"]

    _region = os.environ.get("CDK_DEPLOY_REGION", os.environ["CDK_DEFAULT_REGION"])
    _account = os.environ.get("CDK_DEPLOY_ACCOUNT", os.environ["CDK_DEFAULT_ACCOUNT"])

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.Vpc,
        ecr_registry: ecr.Repository,
        s3_bucket: s3.IBucket,
        lustre_fs: fsx.LustreFileSystem = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        subnet_selection = ec2.SubnetSelection(
            subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
        )

        # Security Group
        sg_batch = ec2.SecurityGroup(
            self,
            id="sg-batch",
            vpc=vpc,
            description="AWS Batch ffmpeg workers",
        )

        # IAM
        batch_instance_role = iam.Role(
            self,
            "batch-job-instance-role",
            # role_name="batch-ffmpeg-instance-role",
            description="AWS Batch with FFMPEG : IAM Instance Role used by Instance Profile in AWS Batch Compute Environment",
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

        batch_job_role = iam.Role(
            self,
            "batch-job-role",
            # role_name="batch-ffmpeg-job-role",
            description="AWS Batch with FFMPEG : IAM Role for Batch Container Job Definition",
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
                                f"arn:aws:ssm:{self._region}:{self._account}"
                                f":parameter/batch-ffmpeg/*",
                                f"arn:aws:ssm:{self._region}:{self._account}"
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
            "batch-ffmpeg-job-execution-role",
            # role_name="batch-ffmpeg-job-execution-role",
            description="AWS Batch with FFMPEG : IAMExecution Role for Batch Container Job Definition",
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

        # EC2 > AMIs
        # TODO Update to Amazon Linux 2023 when Lustre client will be available : https://github.com/amazonlinux/amazon-linux-2023/issues/309
        ecs_amd64_ami = ec2.MachineImage.from_ssm_parameter(
            "/aws/service/ecs/optimized-ami/amazon-linux-2/recommended/image_id"
        )
        ecs_arm64_ami = ec2.MachineImage.from_ssm_parameter(
            "/aws/service/ecs/optimized-ami/amazon-linux-2/arm64/recommended/image_id"
        )
        ecs_nvidia_ami = ec2.MachineImage.from_ssm_parameter(
            "/aws/service/ecs/optimized-ami/amazon-linux-2/gpu/recommended/image_id"
        )
        ecs_xilinx_ami = None
        if self._region in self._xilinx_regions:
            # AWS Marketplace : "AMD Xilinx Video SDK AMI with ECS support for VT1 Instances (AL2)"
            ecs_xilinx_ami = ec2.MachineImage.from_ssm_parameter(
                "/aws/service/marketplace/prod-sw4gdej5auini/3.0.0"
            )

        # AWS Batch > Compute Environment : Instance classes

        # nvidia
        batch_compute_instance_classes_nvidia = [ec2.InstanceClass.G4DN]
        if self._region not in ["eu-west-3"]:
            instances_classes_not_available = [ec2.InstanceClass.G5]
            # Concatenate all sequences
            batch_compute_instance_classes_nvidia = [
                *batch_compute_instance_classes_nvidia,
                *instances_classes_not_available,
            ]

        # intel
        batch_compute_instance_classes_intel = [
            ec2.InstanceClass.C5,
            ec2.InstanceClass.C5N,
            ec2.InstanceClass.C5D,
            ec2.InstanceClass.C6I,
            ec2.InstanceClass.C6IN,
            ec2.InstanceClass.M5,
            ec2.InstanceClass.M5D,
            ec2.InstanceClass.M6I,
        ]
        if self._region not in [
            "ap-south-1",
            "ap-southeast-2",
            "eu-west-3",
            "sa-east-1",
        ]:
            instances_classes_not_available = [
                ec2.InstanceClass.M5N,
                ec2.InstanceClass.C6ID,
                ec2.InstanceClass.M6ID,
                # TODO Waiting deployment
                # ec2.InstanceClass.M7I,
            ]
            # Concatenate all sequences
            batch_compute_instance_classes_intel = [
                *batch_compute_instance_classes_intel,
                *instances_classes_not_available,
            ]

        # arm
        batch_compute_instances_classes_arm = [
            ec2.InstanceClass.C6G,
            ec2.InstanceClass.C6GD,
            ec2.InstanceClass.C6GN,
            ec2.InstanceClass.M6G,
        ]
        if self._region not in [
            "ap-southeast-2",
            "ap-south-1",
            "eu-central-1",
            "sa-east-1",
            "eu-west-3",
            "sa-east-1",
        ]:
            instances_classes_not_available = [
                ec2.InstanceClass.M6GD,
                ec2.InstanceClass.C7G,
                # TODO Waiting deployment
                # ec2.InstanceClass.C7GD,
                ec2.InstanceClass.M7G,
                # TODO Waiting deployment
                # ec2.InstanceClass.M7GD,
            ]
            # Concatenate all sequences
            batch_compute_instances_classes_arm = [
                *batch_compute_instances_classes_arm,
                *instances_classes_not_available,
            ]

        # amd
        batch_compute_instances_classes_amd = [
            ec2.InstanceClass.C5A,
            ec2.InstanceClass.M5A,
            ec2.InstanceClass.M5AD,
        ]
        if self._region not in ["ap-south-1", "eu-west-3"]:
            instances_classes_not_available = [
                ec2.InstanceClass.C5AD,
                ec2.InstanceClass.C6A,
                ec2.InstanceClass.M6A,
                # TODO Waiting deployment
                # ec2.InstanceClass.M7A,
                # ec2.InstanceClass.C7A,
            ]
            # Concatenate all sequences
            batch_compute_instances_classes_amd = [
                *batch_compute_instances_classes_amd,
                *instances_classes_not_available,
            ]

        # batch_compute_instances_classes_xilinx = [ec2.InstanceClass.VT1]
        batch_compute_instances_types_xilinx = [
            ec2.InstanceType.of(ec2.InstanceClass.VT1, ec2.InstanceSize.XLARGE3)
        ]

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

        # AWS Batch : Job Definition > Container
        job_definition_container_env_base = {
            "AWS_XRAY_SDK_ENABLED": "true",
            "S3_BUCKET": s3_bucket.bucket_name,
        }

        job_definition_container_env = job_definition_container_env_base.copy()
        lustre_volumes = None
        if lustre_fs:
            # Mounting FSx for Lustre on an AWS Fargate launch type isn't supported.
            job_definition_container_env["FSX_MOUNT_POINT"] = self.mount_lustre_path
            lustre_volumes = [
                batch.HostVolume(
                    host_path=self.mount_lustre_path,
                    name="fsx-lustre-vol-name",
                    container_path=self.mount_lustre_path,
                )
            ]

        nvidia_tag = "6.0-nvidia2004-amd64"
        batch_jobdef_nvidia_container = batch.EcsEc2ContainerDefinition(
            self,
            "container-def-nvidia",
            image=ecs.ContainerImage.from_ecr_repository(ecr_registry, nvidia_tag),
            command=ffmpeg_python_script_command,
            environment=job_definition_container_env,
            execution_role=batch_execution_role,
            job_role=batch_job_role,
            gpu=1,
            cpu=2,
            memory=cdk.Size.mebibytes(8192),
            volumes=lustre_volumes,
        )
        amd64_tag = "6.0-ubuntu2004-amd64"
        batch_jobdef_amd64_container = batch.EcsEc2ContainerDefinition(
            self,
            "container-def-amd64",
            image=ecs.ContainerImage.from_ecr_repository(ecr_registry, amd64_tag),
            command=ffmpeg_python_script_command,
            environment=job_definition_container_env,
            execution_role=batch_execution_role,
            job_role=batch_job_role,
            gpu=None,
            cpu=2,
            memory=cdk.Size.mebibytes(8192),
            volumes=lustre_volumes,
        )

        arm64_tag = "6.0-ubuntu2004-arm64"
        batch_jobdef_arm64_container = batch.EcsEc2ContainerDefinition(
            self,
            "container-def-arm64",
            image=ecs.ContainerImage.from_ecr_repository(ecr_registry, arm64_tag),
            command=ffmpeg_python_script_command,
            environment=job_definition_container_env,
            execution_role=batch_execution_role,
            job_role=batch_job_role,
            gpu=None,
            cpu=2,
            memory=cdk.Size.mebibytes(8192),
            volumes=lustre_volumes,
        )

        batch_jobdef_fargate_container = batch.EcsFargateContainerDefinition(
            self,
            "container-def-fargate",
            image=ecs.ContainerImage.from_ecr_repository(ecr_registry, amd64_tag),
            command=ffmpeg_python_script_command,
            environment=job_definition_container_env_base,  # TODO Lustre not available for Fargate : https://github.com/aws/containers-roadmap/issues/650
            cpu=2,
            memory=cdk.Size.mebibytes(8192),
            fargate_platform_version=ecs.FargatePlatformVersion.LATEST,
            execution_role=batch_execution_role,
            job_role=batch_job_role,
            volumes=None,  # TODO Lustre not available for Fargate : https://github.com/aws/containers-roadmap/issues/650
        )

        xilinx_tag = "4.4-xilinx2004-amd64"
        # https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ecs-vt1.html
        xilinx_linux_parameters = batch.LinuxParameters(self, "xilinx-linux-param")
        xilinx_linux_parameters.add_devices(
            batch.Device(
                container_path="/sys/bus/pci/devices",
                host_path="/sys/bus/pci/devices",
                permissions=[
                    batch.DevicePermission.READ,
                    batch.DevicePermission.WRITE,
                ],
            ),
            batch.Device(
                container_path="/dev/dri",
                host_path="/dev/dri",
                permissions=[
                    batch.DevicePermission.READ,
                    batch.DevicePermission.WRITE,
                ],
            ),
        )
        job_definition_container_env_xilinx = {
            "XILINX_VISIBLE_DEVICES": "0,1",
        }
        job_definition_container_env_xilinx = {
            **job_definition_container_env_xilinx,
            **job_definition_container_env_base,  # TODO Lustre not available for Xilinx : https://github.com/Xilinx/video-sdk/issues/85
        }
        batch_jobdef_xilinx_container = batch.EcsEc2ContainerDefinition(
            self,
            "container-def-xilinx",
            image=ecs.ContainerImage.from_ecr_repository(ecr_registry, xilinx_tag),
            command=ffmpeg_python_script_command,
            linux_parameters=xilinx_linux_parameters,
            environment=job_definition_container_env_xilinx,
            job_role=batch_job_role,
            gpu=None,
            cpu=2,
            memory=cdk.Size.mebibytes(8192),
            privileged=True,
            volumes=None,  # TODO Lustre not available for Xilinx : https://github.com/Xilinx/video-sdk/issues/85
        )

        # AWS Batch > Job definition, Queue, Compute Environment
        ffmpeg_nvidia_job = VideoBatchJob(
            self,
            construct_id="nvidia-job",
            proc_name="nvidia",
            ec2_ami=ecs_nvidia_ami,
            ec2_vpc=vpc,
            ec2_vpc_sg=sg_batch,
            ec2_vpc_subnets=subnet_selection,
            batch_compute_instance_classes=batch_compute_instance_classes_nvidia,
            batch_jobdef_container=batch_jobdef_nvidia_container,
            batch_jobdef_parameters=ffmpeg_python_script_default_values,
            batch_compute_env_instance_role=batch_instance_role,
            lustre_fs=lustre_fs,
        )
        self.video_batch_jobs.append(ffmpeg_nvidia_job)

        if self._region in self._xilinx_regions:
            ffmpeg_xilinx_job = VideoBatchJob(
                self,
                construct_id="xilinx-job",
                proc_name="xilinx",
                ec2_ami=ecs_xilinx_ami,
                ec2_vpc=vpc,
                ec2_vpc_sg=sg_batch,
                ec2_vpc_subnets=subnet_selection,
                batch_compute_instance_classes=None,
                batch_compute_instance_types=batch_compute_instances_types_xilinx,
                batch_jobdef_container=batch_jobdef_xilinx_container,
                batch_jobdef_parameters=ffmpeg_python_script_default_values,
                batch_compute_env_instance_role=batch_instance_role,
                lustre_fs=lustre_fs,
            )
            self.video_batch_jobs.append(ffmpeg_xilinx_job)

        ffmpeg_intel_job = VideoBatchJob(
            self,
            construct_id="intel-job",
            proc_name="intel",
            ec2_ami=ecs_amd64_ami,
            ec2_vpc=vpc,
            ec2_vpc_sg=sg_batch,
            ec2_vpc_subnets=subnet_selection,
            batch_compute_instance_classes=batch_compute_instance_classes_intel,
            batch_jobdef_container=batch_jobdef_amd64_container,
            batch_jobdef_parameters=ffmpeg_python_script_default_values,
            batch_compute_env_instance_role=batch_instance_role,
            lustre_fs=lustre_fs,
        )
        self.video_batch_jobs.append(ffmpeg_intel_job)

        ffmpeg_amd_job = VideoBatchJob(
            self,
            construct_id="amd-job",
            proc_name="amd",
            ec2_ami=ecs_amd64_ami,
            ec2_vpc=vpc,
            ec2_vpc_sg=sg_batch,
            ec2_vpc_subnets=subnet_selection,
            batch_compute_instance_classes=batch_compute_instances_classes_amd,
            batch_jobdef_container=batch_jobdef_amd64_container,
            batch_jobdef_parameters=ffmpeg_python_script_default_values,
            batch_compute_env_instance_role=batch_instance_role,
            lustre_fs=lustre_fs,
        )
        self.video_batch_jobs.append(ffmpeg_amd_job)

        ffmpeg_arm_job = VideoBatchJob(
            self,
            construct_id="arm-job",
            proc_name="arm",
            ec2_ami=ecs_arm64_ami,
            ec2_vpc=vpc,
            ec2_vpc_sg=sg_batch,
            ec2_vpc_subnets=subnet_selection,
            batch_compute_instance_classes=batch_compute_instances_classes_arm,
            batch_jobdef_container=batch_jobdef_arm64_container,
            batch_jobdef_parameters=ffmpeg_python_script_default_values,
            batch_compute_env_instance_role=batch_instance_role,
            lustre_fs=lustre_fs,
        )
        self.video_batch_jobs.append(ffmpeg_arm_job)

        ffmpeg_fargate_job = VideoBatchJob(
            self,
            construct_id="fargate-job",
            proc_name="fargate",
            ec2_ami=None,
            ec2_vpc=vpc,
            ec2_vpc_sg=sg_batch,
            ec2_vpc_subnets=subnet_selection,
            batch_compute_instance_classes=None,
            batch_jobdef_container=batch_jobdef_fargate_container,
            batch_jobdef_parameters=ffmpeg_python_script_default_values,
            batch_compute_env_instance_role=None,
        )
        self.video_batch_jobs.append(ffmpeg_fargate_job)

        # TODO Waiting : https://github.com/aws/aws-cdk/issues/26484 and https://github.com/aws/aws-cdk/pull/26506
        # ffmpeg_fargate_arm_job = VideoBatchJob(
        #     self,
        #     construct_id="fargate-arm-job",
        #     proc_name="fargate-arm",
        #     ec2_ami=None,
        #     ec2_vpc=vpc,
        #     ec2_vpc_sg=sg_batch,
        #     ec2_vpc_subnets=subnets,
        #     batch_compute_instance_classes=None,
        #     batch_jobdef_container=batch_jobdef_fargate_arm_container,
        #     batch_jobdef_parameters=ffmpeg_python_script_default_values,
        #     batch_compute_env_instanceprofile=None,
        # )
        # self.video_batch_jobs.append(ffmpeg_fargate_arm_job)
