"""Utility functions for S3 operations and AWS region detection.

This module provides functions to check S3 object existence and
dynamically determine the AWS region for the running environment.

Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
SPDX-License-Identifier: Apache-2.0
"""

import logging
import os

import boto3
from ec2_metadata import ec2_metadata

# Configure logging
LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
logging.basicConfig(level=LOGLEVEL)
logger = logging.getLogger(__name__)
logging.getLogger("aws_xray_sdk").setLevel(LOGLEVEL)


def detect_running_region() -> str:
    """Dynamically determine the AWS region.

    Returns:
        str: The detected AWS region.

    Raises:
        RuntimeError: If unable to determine the region.
    """
    # Check environment variables
    for env_var in ["AWS_REGION", "AWS_DEFAULT_REGION"]:
        region = os.environ.get(env_var)
        if region:
            return region

    # Check boto3 session
    session = boto3.DEFAULT_SESSION or boto3.Session()
    if session.region_name:
        return session.region_name

    # Query EC2 metadata
    try:
        return ec2_metadata.region
    except Exception as e:
        logger.error(f"Failed to determine region from EC2 metadata: {e}")

    raise RuntimeError("Unable to determine AWS region")
