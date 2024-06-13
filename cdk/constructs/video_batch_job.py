# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0,
from aws_cdk import Duration
from aws_cdk import aws_batch as batch
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_fsx as fsx
from constructs import Construct
from from_root import from_root
import hashlib


class VideoBatchJob(Construct):
    proc_name: str
    job_queue_name: str
    job_queue: batch.IJobQueue
    job_definition_name: str
    job_definition: batch.IJobDefinition

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        proc_name: str,
        batch_jobdef_container,
        batch_jobdef_parameters,
        batch_compute_env_instance_role,
        ec2_vpc: ec2.IVpc,
        ec2_ami: ec2.IMachineImage,
        ec2_vpc_sg,
        ec2_vpc_subnets,
        batch_compute_instance_classes=None,
        batch_compute_instance_types=None,
        lustre_fs: fsx.LustreFileSystem = None,
        spot: bool = True,
    ) -> None:
        super().__init__(scope, construct_id)

        fargate_disabled = batch_compute_instance_classes or ec2_ami

        self.proc_name = proc_name
        self.job_queue_name = "batch-ffmpeg-job-queue-" + proc_name
        self.job_definition_name = "batch-ffmpeg-job-definition-" + proc_name

        batch_job_definition = batch.EcsJobDefinition(
            self,
            id="job-definition",
            job_definition_name=self.job_definition_name,
            container=batch_jobdef_container,
            parameters=batch_jobdef_parameters,
            retry_attempts=1,
            timeout=Duration.hours(10),
        )

        if fargate_disabled:
            # Multipart User Data
            multipart_user_data = ec2.MultipartUserData()
            with open(from_root("cdk", "constructs", "user_data_xray.txt")) as f:
                user_data_xray_txt = f.read()
                multipart_user_data.add_part(
                    ec2.MultipartBody.from_raw_body(
                        content_type='text/x-shellscript; charset="us-ascii"',
                        body=user_data_xray_txt,
                    )
                )
            if lustre_fs:
                # BUG issue with GPU AMI https://github.com/aws/amazon-ecs-ami/pull/191
                if proc_name in ["xilinx", "nvidia"]:
                    with open(from_root("cdk", "constructs", "user_data_gpu.txt")) as f:
                        user_data_gpu_txt = f.read()
                        multipart_user_data.add_part(
                            ec2.MultipartBody.from_raw_body(
                                content_type='text/x-shellscript; charset="us-ascii"',
                                body=user_data_gpu_txt,
                            )
                        )
                with open(from_root("cdk", "constructs", "user_data_lustre.txt")) as f:
                    user_data_lustre_txt = f.read()
                    user_data_lustre_txt = user_data_lustre_txt.replace(
                        "%DNS_NAME%", lustre_fs.dns_name
                    )
                    user_data_lustre_txt = user_data_lustre_txt.replace(
                        "%MOUNT_NAME%", lustre_fs.mount_name
                    )
                    user_data_lustre_txt = user_data_lustre_txt.replace(
                        "%MOUNT_POINT%", "/fsx-lustre"
                    )

                    multipart_user_data.add_part(
                        ec2.MultipartBody.from_raw_body(
                            content_type='text/x-shellscript; charset="us-ascii"',
                            body=user_data_lustre_txt,
                        )
                    )

            # Launch Template
            md5_hash = hashlib.md5(
                multipart_user_data.render().encode(), usedforsecurity=False
            )
            short_hash = md5_hash.hexdigest()[:5]

            launch_template = ec2.LaunchTemplate(
                self,
                "lt-" + proc_name + "-" + short_hash,
                launch_template_name="batch-ffmpeg-lt-" + proc_name + "-" + short_hash,
                user_data=multipart_user_data,
            )
            compute_environment = batch.ManagedEc2EcsComputeEnvironment(
                self,
                "batch-ec2-compute-environment-" + proc_name,
                vpc=ec2_vpc,
                images=[{"image": ec2_ami}],
                instance_classes=batch_compute_instance_classes,
                instance_types=batch_compute_instance_types
                if batch_compute_instance_classes is None
                else None,
                use_optimal_instance_classes=False,
                update_to_latest_image_version=True,
                instance_role=batch_compute_env_instance_role,
                terminate_on_update=False,
                launch_template=launch_template,
                security_groups=[ec2_vpc_sg],
                vpc_subnets=ec2_vpc_subnets,
                spot=spot,
                maxv_cpus=4096,
            )
        else:
            compute_environment = batch.FargateComputeEnvironment(
                self,
                "batch-fargate-compute-environment-" + proc_name,
                vpc=ec2_vpc,
                security_groups=[ec2_vpc_sg],
                vpc_subnets=ec2_vpc_subnets,
                spot=spot,
            )
        compute_environment.node.add_dependency(ec2_vpc_sg)
        # Job Queue
        batch_job_queue = batch.JobQueue(
            self,
            "job-queue",
            job_queue_name=self.job_queue_name,
            priority=1,
        )
        batch_job_queue.add_compute_environment(compute_environment, 1)

        self.job_definition = batch_job_definition
        self.job_queue = batch_job_queue
        self.job_queue_arn = batch_job_queue.job_queue_arn
        self.job_definition_arn = batch_job_definition.job_definition_arn
