# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
from constructs import Construct
from aws_cdk import (
    Duration,
    aws_ec2 as ec2,
    aws_batch_alpha as batch,
)
import aws_cdk as cdk
from from_root import from_root


class VideoBatchJob(Construct):
    type: str
    job_queue_name: str
    job_queue: batch.IJobQueue
    job_definition_name: str
    job_definition: batch.IJobDefinition

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        type: str,
        batch_compute_instancetypes,
        batch_jobdef_container,
        batch_jobdef_parameters,
        batch_compute_env_instanceprofile_arn,
        ec2_vpc: ec2.IVpc,
        ec2_ami: ec2.IMachineImage,
        ec2_vpc_sg,
        ec2_vpc_subnets,
        **kwargs
    ) -> None:

        super().__init__(scope, construct_id, **kwargs)

        fargate_disabled = True if (batch_compute_instancetypes or ec2_ami) else False

        # Source : https://github.com/aws-samples/aws-cdk-deep-learning-image-vector-embeddings-at-scale-using-aws-batch/blob/main/batch_job_cdk/stack.py
        # Source : https://github.com/aws-samples/aws-batch-xray/blob/main/lib/batch-xray-stack.ts

        self.type = type
        self.job_queue_name = "batch-ffmpeg-job-queue-" + type
        self.job_definition_name = "batch-ffmpeg-job-definition-" + type

        batch_job_definition = batch.JobDefinition(
            self,
            id="job-definition",
            job_definition_name=self.job_definition_name,
            container=batch_jobdef_container,
            parameters=batch_jobdef_parameters,
            retry_attempts=1,
            timeout=Duration.minutes(90),
            platform_capabilities=[
                batch.PlatformCapabilities.EC2
                if fargate_disabled
                else batch.PlatformCapabilities.FARGATE
            ],
        )

        # Compute Environment
        with open(from_root("cdk", "constructs", "user_data.txt")) as f:
            txt = f.read()

        batch_launch_template = ec2.CfnLaunchTemplate(
            self,
            "launch-template",
            launch_template_name=type + "-batch-launch-template",
            launch_template_data=ec2.CfnLaunchTemplate.LaunchTemplateDataProperty(
                user_data=cdk.Fn.base64(txt)
            ),
        )
        batch_launch_template_spec = batch.LaunchTemplateSpecification(
            launch_template_name=batch_launch_template.launch_template_name
        )

        compute_environment = batch.ComputeEnvironment(
            self,
            "batch-compute-environment",
            compute_resources=batch.ComputeResources(
                vpc=ec2_vpc,
                image=ec2_ami,
                instance_types=batch_compute_instancetypes,
                instance_role=batch_compute_env_instanceprofile_arn,
                security_groups=[ec2_vpc_sg],
                vpc_subnets=ec2_vpc_subnets,
                compute_resources_tags={"type": type, "application": "batch-ffmpeg"}
                if fargate_disabled
                else None,
                type=batch.ComputeResourceType.SPOT
                if fargate_disabled
                else batch.ComputeResourceType.FARGATE,
                bid_percentage=90 if fargate_disabled else None,
                launch_template=batch_launch_template_spec
                if fargate_disabled
                else None,
            ),
        )
        compute_environment.node.add_dependency(ec2_vpc_sg)

        # Job Queue
        batch_job_queue = batch.JobQueue(
            self,
            "job-queue",
            job_queue_name=self.job_queue_name,
            priority=1,
            compute_environments=[
                batch.JobQueueComputeEnvironment(
                    compute_environment=compute_environment, order=1
                )
            ],
        )
        self.job_definition = batch_job_definition
        self.job_queue = batch_job_queue
        self.job_queue_arn = batch_job_queue.job_queue_arn
        self.job_definition_arn = batch_job_definition.job_definition_arn
