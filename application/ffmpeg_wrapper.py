# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
import json
from subprocess import Popen, PIPE
import sys
import os
import logging
import tempfile
import shutil
import shlex
import time
import pprint
import click

import boto3
from botocore.exceptions import ClientError
from aws_xray_sdk.core import xray_recorder
from aws import aws_helper
from aws.s3_url import S3Url
from ffmpeg_quality_metrics import (
    FfmpegQualityMetrics as ffqm,
)

xray_recorder.configure(sampling=False)

LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
logging.basicConfig(level=LOGLEVEL)
logging.getLogger("aws_xray_sdk").setLevel(LOGLEVEL)


@click.command(name="main")
@click.option("--global_options", help="ffmpeg global options", type=str)
@click.option("--input_file_options", help="ffmpeg input file options", type=str)
@click.option("--input_url", help="Amazon S3 input url", type=str)
@click.option("--output_file_options", help="ffmpeg output file options", type=str)
@click.option("--output_url", help="Amazon S3 output url", type=str)
@click.option("--name", help="Optional name to identify cmd in logs", type=str)
def main(
    global_options, input_file_options, input_url, output_file_options, output_url, name
):
    """Python CLI for FFMPEG with Amazon S3 download/upload and video quality metrics"""

    aws_region = aws_helper.detect_running_region()
    ssm_client = boto3.client("ssm", region_name=aws_region)
    s3_client = boto3.client("s3", region_name=aws_region)

    # Arguments validation
    logging.info("global_options: %s", global_options)
    logging.info("input_file_options : %s", input_file_options)
    logging.info("input_url : %s", input_url)
    logging.info("output_file_options : %s", output_file_options)
    logging.info("output_url : %s", output_url)
    logging.info("name : %s", name)

    if global_options == "null":
        global_options = None
    if input_file_options == "null":
        input_file_options = None
    if input_url == "null":
        input_url = None
    if output_file_options == "null":
        output_file_options = None
    if output_url == "null":
        output_url = None
    if name == "null":
        name = None

    # Get env variables
    aws_batch_job_id = os.getenv("AWS_BATCH_JOB_ID", "local")
    aws_batch_jq_name = os.getenv("AWS_BATCH_JQ_NAME", "local")
    aws_batch_ce_name = os.getenv("AWS_BATCH_CE_NAME", "local")
    s3_bucket_stack = os.getenv("S3_BUCKET", None)
    logging.info(
        "AWS Batch JobId = %s - AWS Batch Job Queue Name = %s - AWS Batch Compute Env. = %s",
        aws_batch_job_id,
        aws_batch_jq_name,
        aws_batch_ce_name,
    )

    # Get AWS parameters
    try:
        parameter = ssm_client.get_parameter(
            Name="/batch-ffmpeg/ffqm", WithDecryption=False
        )
        metrics_flag = parameter["Parameter"]["Value"]

    except ClientError:
        logging.error("metrics flag not found in SSM Parameter")
        metrics_flag = "FALSE"

    # AWS X Ray Recorder configuration
    xray_recorder.configure(plugins=["EC2Plugin", "ECSPlugin"])

    segment = xray_recorder.begin_segment("batch-ffmpeg-job")
    segment.put_metadata("execution", "ffmpeg-wrapper-" + time.strftime("%Y%m%d-%H%M%S"))
    segment.put_annotation("application", "ffmpeg-wrapper")
    segment.put_annotation("global_options", global_options)
    segment.put_annotation("input_file_options", input_file_options)
    segment.put_annotation("input_url", input_url)
    segment.put_annotation("output_file_options", output_file_options)
    segment.put_annotation("output_url", output_url)
    segment.put_annotation("name", name)
    segment.put_annotation("AWS_BATCH_JOB_ID", aws_batch_job_id)
    segment.put_annotation("AWS_BATCH_JQ_NAME", aws_batch_jq_name)
    segment.put_annotation("AWS_BATCH_CE_NAME", aws_batch_ce_name)

    # Prepare temp files
    tmp_dir = tempfile.TemporaryDirectory(prefix="ffmpeg_workdir_").name + "/"
    logging.info("tmp dir is %s", tmp_dir)
    parse_output_url = S3Url(output_url)
    bucket_output = parse_output_url.bucket
    key_output = parse_output_url.key
    tmp_output = tmp_dir + key_output
    tmp_dir_output = os.path.dirname(tmp_output) + "/"
    os.makedirs(tmp_dir_output, exist_ok=True)

    # Download media assets from S3 bucket
    try:
        input_urls = input_url.replace(" ", "").split(",")
        files = download_s3_files(s3_client, input_urls, tmp_dir)
    except Exception as e:
        logging.error("Download Error :  {}".format(e))
        sys.exit(1)

    # ffmpeg command creation
    command_list = ["ffmpeg"]
    if global_options:
        command_list = command_list + shlex.split(global_options)
    if input_url:
        if input_file_options:
            command_list = command_list + shlex.split(input_file_options)
        for file in files:
            command_list.append("-i")
            command_list.append(file)
    if output_url:
        if output_file_options:
            command_list = command_list + shlex.split(output_file_options)
        command_list.append(tmp_output)

    # ffmpeg execution
    logging.info("ffmpeg command to launch : %s", " ".join(command_list))
    subsegment = xray_recorder.begin_subsegment("cmd-execution")
    subsegment.put_metadata("command", " ".join(command_list))

    p = Popen(command_list, stdout=PIPE, stderr=PIPE)
    output, error = p.communicate()
    if p.returncode != 0:
        logging.error("ffmpeg failed - return code : %d", p.returncode)
        logging.error("ffmpeg failed - output : %s", output)
        logging.error("ffmpeg failed - error : %s", error)
        sys.exit(1)

    logging.info("ffmpeg succeeded %d %s %s", p.returncode, output, error)
    xray_recorder.end_subsegment()

    # Uploading media output to Amazon S3
    try:
        if "%" in key_output:
            # Sync output directory
            tmp_output = tmp_dir_output
            split = key_output.split("/")
            key_output = "/".join(split[:-1])
            sync_dir_to_s3(s3_client, tmp_output, bucket_output, key_output)
        else:
            # Upload a file
            upload_file_to_s3(s3_client, tmp_output, bucket_output, key_output)
    except Exception as e:
        logging.error(
            "The app can not upload %s on this S3 bucket (%s - %s)",
            tmp_dir_output,
            bucket_output,
            key_output,
        )
        logging.error("Upload Error :  {}".format(e))
        sys.exit(1)

    logging.info(
        "Done : ffmpeg results uploaded to %s - key_output : %s",
        bucket_output,
        key_output,
    )

    # Calculate video quality metrics
    try:
        banned_formats = ["%", ".m4a", ".mp3"]
        if metrics_flag == "TRUE" and (len(files) == 1 and (not any(x in output_url for x in banned_formats))):
            logging.info("Compute video quality metrics")
            metrics = quality_metrics(files[0], tmp_output)
            metrics["AWS_BATCH_JOB_ID"] = aws_batch_job_id
            metrics["AWS_BATCH_JQ_NAME"] = aws_batch_jq_name
            metrics["AWS_BATCH_CE_NAME"] = aws_batch_ce_name
            save_qm_s3(s3_client, s3_bucket_stack, metrics)
        else:
            logging.warning(
                "You can't compute quality metrics with this command %s", name
            )
    except Exception as e:
        logging.error("Quality Metrics Error :  {}".format(e))

    # Clean
    shutil.rmtree(tmp_dir, ignore_errors=True)
    xray_recorder.end_segment()
    sys.exit(0)


@xray_recorder.capture("quality-metrics")
def quality_metrics(input: str, output: str):
    """Compute quality metrics"""

    logging.info("ffqm reference file : %s  - distorded file : %s", input, output)
    f = ffqm(input, output)
    full = f.calculate(metrics=["ssim", "psnr", "vmaf"])
    summary = f.get_global_stats()
    document = xray_recorder.current_subsegment()
    document.put_metadata("quality_metrics", summary)
    logging.info("quality metrics : %s", pprint.pformat(summary))
    return full


def save_qm_s3(s3_client, s3_bucket, document: dict):
    """save quality metrics on Amazon S3"""
    key = (
        "metrics/ffqm/"
        + time.strftime("year=%Y/month=%b/day=%d")
        + "/"
        + document["AWS_BATCH_JQ_NAME"]
        + "_"
        + document["AWS_BATCH_CE_NAME"]
        + "_"
        + document["AWS_BATCH_JOB_ID"]
        + ".json"
    )
    logging.info("Saving quality metrics in (%s - %s)", s3_bucket, key)
    s3_client.put_object(Bucket=s3_bucket, Key=key, Body=json.dumps(document))


@xray_recorder.capture("download")
def download_s3_files(s3_client, s3_urls: list, dir):
    """Download a list of Amazon S3 URLs to a directory"""
    files = []
    for s3_url in s3_urls:
        parse = S3Url(s3_url)
        s3_bucket = parse.bucket
        s3_key = parse.key
        path_file = dir + s3_key
        path_dir = os.path.dirname(path_file)
        os.makedirs(path_dir, exist_ok=True)
        logging.info(
            "Downloading S3 object from (bucket:%s - key:%s) to %s",
            s3_bucket,
            s3_key,
            path_file,
        )
        s3_client.download_file(s3_bucket, s3_key, path_file)
        files.append(path_file)
    return files


@xray_recorder.capture("upload")
def upload_file_to_s3(s3_client, file, s3_bucket, s3_key):
    """Upload file to Amazon S3 bucket"""
    logging.info('Searching "%s" in "%s"', s3_key, s3_bucket)
    # Check if object already exists on S3 and skip upload if it does
    try:
        s3_client.head_object(Bucket=s3_bucket, Key=s3_key)
        # Object found on S3, skip upload
        logging.info("Path found on S3! Skipping %s...", s3_key)
    # Object was not found on S3, proceed to upload
    except ClientError:
        logging.info("Uploading %s in %s", file, s3_key)
        s3_client.upload_file(file, s3_bucket, s3_key)


@xray_recorder.capture("upload")
def sync_dir_to_s3(s3_client, source_dir, s3_bucket, s3_key):
    """Sync `source_dir` directory to Amazon S3 bucket"""
    logging.info("Sync of %s to %s - %s", source_dir, s3_bucket, s3_key)
    for root, dirs, files in os.walk(source_dir):
        for filename in files:
            # construct the full local path
            local_path = os.path.join(root, filename)
            # construct the full S3 path
            relative_path = os.path.relpath(local_path, source_dir)
            s3_path = os.path.join(s3_key, relative_path)
            # Upload file to S3
            upload_file_to_s3(s3_client, local_path, s3_bucket, s3_path)


if __name__ == "__main__":
    main()
