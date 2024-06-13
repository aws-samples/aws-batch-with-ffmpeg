# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0,
import logging
import os
import hashlib
import yaml
from aws_cdk import Aws as aws
import aws_cdk as cdk
from aws_cdk import Fn as fn
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_fsx as fsx
from aws_cdk import aws_iam as iam
from aws_cdk import aws_ssm as ssm
from constructs import Construct
from from_root import from_root

try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
logging.basicConfig(level=LOGLEVEL)
logger = logging.getLogger()
logger.setLevel(LOGLEVEL)


class SSMDocumentLustrePreload(Construct):
    ssm_document: ssm.CfnDocument

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        subnet: ec2.Subnet,
        lustre_fs: fsx.LustreFileSystem = None,
    ) -> None:
        super().__init__(scope, construct_id)
        ec2_ami = ec2.MachineImage.from_ssm_parameter(
            "/aws/service/ecs/optimized-ami/amazon-linux-2/recommended/image_id"
        )
        # EC2 Role
        ec2_ssm_role = iam.Role(
            self,
            "ssm-ec2-instance-role",
            description="AWS Batch with FFMPEG : Enables EC2 to access SSM",
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("ec2.amazonaws.com"),
            ),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonEC2RoleforSSM"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonSSMManagedInstanceCore"
                ),
            ],
        )
        ec2_ssm_instance_profile = iam.InstanceProfile(
            self,
            "ssm-ec2-instance-profile",
            role=ec2_ssm_role,
        )
        # IAM assume role for the execution of the SSM Automation
        ssm_assume_role = iam.Role(
            self,
            "ssm-assume-role",
            description="AWS Batch with FFMPEG : SSM assume role",
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("ssm.amazonaws.com"),
            ),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonSSMAutomationRole"
                ),
            ],
            inline_policies={
                "pass-role": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "iam:PassRole",
                            ],
                            resources=[
                                "arn:"
                                + aws.PARTITION
                                + ":iam::"
                                + aws.ACCOUNT_ID
                                + f":role/{ec2_ssm_role.role_name}"
                            ],
                        )
                    ]
                )
            },
        )

        # EC2 UserData
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

        user_data_lustre_base64 = fn.base64(user_data_lustre_txt)
        md5_hash = hashlib.md5(user_data_lustre_txt.encode(), usedforsecurity=False)
        short_hash = md5_hash.hexdigest()[:5]

        # SSM Automation Document YAML
        with open(from_root("cdk", "ssm-documents", "lustre-preload.yaml")) as f:
            lustre_preload_document_yaml = f.read()
            lustre_preload_document_yaml = lustre_preload_document_yaml.replace(
                "%IMAGE_ID%", ec2_ami.get_image(self).image_id
            )
            lustre_preload_document_yaml = lustre_preload_document_yaml.replace(
                "%SUBNET_ID%", subnet.subnet_id
            )
            lustre_preload_document_yaml = lustre_preload_document_yaml.replace(
                "%USER_DATA%", user_data_lustre_base64
            )
            lustre_preload_document_yaml = lustre_preload_document_yaml.replace(
                "%ROLE_ARN%", ssm_assume_role.role_arn
            )
            lustre_preload_document_yaml = lustre_preload_document_yaml.replace(
                "%INSTANCE_PROFILE_ARN%", ec2_ssm_instance_profile.instance_profile_arn
            )
            lustre_preload_document_yaml = lustre_preload_document_yaml.replace(
                "%HASH_USERDATA%", short_hash
            )

            self.ssm_document = ssm.CfnDocument(
                self,
                "ssm-automation",
                content=yaml.load(lustre_preload_document_yaml, Loader=Loader),
                document_type="Automation",
                document_format="YAML",
                name="batch-ffmpeg-lustre-preload",
                update_method="NewVersion",
                tags=[cdk.CfnTag(key="hash-user-data", value=short_hash)],
            )
