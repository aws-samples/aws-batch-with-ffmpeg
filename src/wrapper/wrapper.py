import errno
import json
import logging
import os
import shlex
import subprocess  # nosec B404
import sys
import tempfile
import time
from typing import List, Tuple

import boto3
import click
from aws_xray_sdk.core import xray_recorder
from botocore.exceptions import ClientError

from shared_libraries import aws
from shared_libraries import aws_s3
from shared_libraries.aws_s3 import S3Url
from ffmpeg_quality_metrics import FfmpegQualityMetrics as ffqm

# X-Ray configuration
xray_recorder.configure(
    sampling=False, plugins=["EC2Plugin", "ECSPlugin"], context_missing="LOG_ERROR"
)

# Logging configuration
LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
logging.basicConfig(level=LOGLEVEL)
logging.getLogger("aws_xray_sdk").setLevel(LOGLEVEL)


def configure_aws_clients(aws_region: str):
    logging.info(f"Using AWS region: {aws_region}")
    return boto3.client("ssm", region_name=aws_region), boto3.client(
        "s3", region_name=aws_region
    )


def get_ssm_parameter(ssm_client, parameter_name: str, default_value: str) -> str:
    try:
        parameter = ssm_client.get_parameter(Name=parameter_name, WithDecryption=False)
        return parameter["Parameter"]["Value"]
    except ClientError as e:
        logging.error(
            f"{parameter_name} not found in SSM Parameter - Error message : {str(e)}"
        )
        return default_value


def prepare_assets(
    input_url: str, output_url: str, fsx_lustre_mount_point: str, s3_client
) -> Tuple[List[str], str, tempfile.TemporaryDirectory]:
    """Prepare media assets by downloading from S3 url to local storage or
    translate urls from S3 to FSx for Lustre path."""
    s3_output_url = S3Url(output_url)
    s3_inputs = input_url.replace(" ", "").split(",")

    if not fsx_lustre_mount_point:
        # Create a temporary directory for S3 downloads
        logging.info(
            "No FSx for Lustre mount point provided, using temporary directory"
        )
        tmp_dir = tempfile.TemporaryDirectory(prefix="ffmpeg_workdir_")
        logging.info(f"Created temporary directory: {tmp_dir.name}")
        output_file_path = os.path.join(tmp_dir.name, s3_output_url.key)
        try:
            input_files_path = aws_s3.download_s3_files(
                s3_client, s3_inputs, tmp_dir.name
            )
        except Exception as e:
            logging.error(f"Download Error: ${s3_inputs} - {e}")
            tmp_dir.cleanup()
            sys.exit(1)
    else:
        # Use FSx for Lustre
        logging.info("Using FSx for Lustre mount point")
        tmp_dir = None
        output_file_path = os.path.join(fsx_lustre_mount_point, s3_output_url.key)
        logging.info(f"Output file path: {output_file_path}")
        input_files_path = []
        for s3_input in s3_inputs:
            s3_input_url = S3Url(s3_input)
            input_file_path = os.path.join(fsx_lustre_mount_point, s3_input_url.key)
            if not os.path.isfile(input_file_path):
                logging.error(f"File {input_file_path} not found on Lustre")
                raise FileNotFoundError(
                    errno.ENOENT, os.strerror(errno.ENOENT), input_file_path
                )
            input_files_path.append(input_file_path)

    # Ensure the output directory exists
    os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
    return input_files_path, output_file_path, tmp_dir


def execute_ffmpeg_command(command_list: List[str]):
    """Execute a FFmpeg command and log the results."""
    logging.info(f"ffmpeg command to launch: {' '.join(command_list)}")

    # Start X-Ray subsegment
    with xray_recorder.in_subsegment("cmd-execution") as subsegment:
        subsegment.put_metadata("command", " ".join(command_list))

        result = subprocess.run(command_list, capture_output=True, text=True)  # nosec B404 B603 B607

        if result.returncode != 0:
            logging.error(f"ffmpeg failed - return code: {result.returncode}")
            logging.error(f"ffmpeg failed - output: {result.stdout}")
            logging.error(f"ffmpeg failed - error: {result.stderr}")
            subsegment.add_exception(
                Exception(
                    f"FFmpeg command failed with return code {result.returncode}"
                ),
                stack=result.stderr,
            )
            raise subprocess.CalledProcessError(
                returncode=result.returncode, cmd=result.args, stderr=result.stderr
            )

        logging.info(
            "ffmpeg succeeded %d - %s - %s",
            result.returncode,
            result.stdout,
            result.stderr,
        )


def nvidia_smi():
    """Execute the nvidia-smi command and log the results.

    Raises:
        SystemExit: If the nvidia-smi command fails.
    """
    result = subprocess.run(["nvidia-smi"], capture_output=True, text=True)  # nosec B404 B603 B607
    if result.returncode != 0:
        logging.error(f"Nvidia smi command failed - return code: {result.returncode}")
        logging.error(f"Nvidia smi command failed - output: {result.stdout}")
        logging.error(f"Nvidia smi command failed - error: {result.stderr}")
        sys.exit(1)
    logging.info(
        f"Nvidia smi command succeeded {result.returncode} {result.stdout} {result.stderr}"
    )


def create_ffmpeg_command(
    global_options,
    input_file_options,
    input_files_path,
    output_file_options,
    output_file_path,
):
    """Create the FFmpeg command list based on the provided options and file
    paths."""
    command_list = ["ffmpeg"]
    if global_options:
        command_list.extend(shlex.split(global_options))
    if input_files_path:
        if input_file_options:
            command_list.extend(shlex.split(input_file_options))
        for file in input_files_path:
            command_list.extend(["-i", file])
    if output_file_path:
        if output_file_options:
            command_list.extend(shlex.split(output_file_options))
        command_list.append(output_file_path)
    return command_list


def upload_to_s3(s3_client, output_file_path, output_url):
    """Upload the output file or directory to S3."""
    s3_output_url = S3Url(output_url)
    try:
        if "%" in s3_output_url.key:
            logging.info("Upload to S3 the whole directory of the output")
            # Sync output directory
            key_output = "/".join(s3_output_url.key.split("/")[:-1])
            aws_s3.sync_dir_to_s3(
                s3_client,
                os.path.dirname(output_file_path) + "/",
                s3_output_url.bucket,
                key_output,
            )
        else:
            # Upload a file
            logging.info(f"Upload to S3 the output file : ${output_file_path}")
            aws_s3.upload_file_to_s3(
                s3_client, output_file_path, s3_output_url.bucket, s3_output_url.key
            )
    except Exception as e:
        logging.error(
            "The app can not upload %s on this S3 bucket (%s - %s)",
            os.path.dirname(output_file_path) + "/",
            s3_output_url.bucket,
            s3_output_url.key,
        )
        logging.error("Upload Error : %s", str(e))
        sys.exit(1)

    logging.info(
        "Done : ffmpeg results uploaded to %s - key_output : %s",
        s3_output_url.bucket,
        s3_output_url.key,
    )


## Quality Metrics
def calculate_quality_metrics(source: str, destination: str) -> dict:
    """Calculate video quality metrics using ffmpeg-quality-metrics."""
    f = ffqm(source, destination)
    logging.info("Calculating quality metrics...")
    full = f.calculate(metrics=["ssim", "psnr", "vmaf"])
    global_stats = f.get_global_stats()
    full["global"] = global_stats
    return full


def save_quality_metrics(s3_client, s3_bucket: str, document: dict):
    """Save quality metrics to an S3 bucket."""
    key = f"metrics/ffqm/{time.strftime('year=%Y/month=%b/day=%d')}/{document['AWS_BATCH_JQ_NAME']}_{document['AWS_BATCH_CE_NAME']}_{document['AWS_BATCH_JOB_ID']}.json"
    logging.info(f"Saving quality metrics to S3 : {s3_bucket}/{key}")
    s3_client.put_object(Bucket=s3_bucket, Key=key, Body=json.dumps(document))


@xray_recorder.capture("quality-metrics")
def quality_metrics(
    input_files_path, output_file_path, output_url, env_vars, s3_client, ssm_client
):
    """Calculate video quality metrics and save them to S3 if conditions are
    met."""
    try:
        banned_formats = ["%", ".m4a", ".mp3"]
        # Get AWS parameters
        metrics_flag = get_ssm_parameter(ssm_client, "/batch-ffmpeg/ffqm", "FALSE")
        logging.info(
            f"Quality metrics flag : {metrics_flag} - Number of source : {len(input_files_path)} - No banned Formats : {not any(x in output_url for x in banned_formats)}"
        )

        if (
            metrics_flag == "TRUE"
            and len(input_files_path) == 1
            and not any(x in output_url for x in banned_formats)
        ):
            metrics = calculate_quality_metrics(input_files_path[0], output_file_path)
            metrics.update(
                {
                    k: env_vars[k]
                    for k in [
                        "AWS_BATCH_JOB_ID",
                        "AWS_BATCH_JQ_NAME",
                        "AWS_BATCH_CE_NAME",
                    ]
                }
            )
            save_quality_metrics(s3_client, env_vars["S3_BUCKET"], metrics)
        else:
            logging.info("Quality metrics not computed")
    except Exception as e:
        logging.error(f"Quality Metrics Error {str(e)}")


@click.command(name="main")
@click.option("--global_options", help="ffmpeg global options", type=str)
@click.option("--input_file_options", help="ffmpeg input file options", type=str)
@click.option("--input_url", help="Amazon S3 input url", type=str, required=True)
@click.option("--output_file_options", help="ffmpeg output file options", type=str)
@click.option("--output_url", help="Amazon S3 output url", type=str, required=True)
@click.option("--name", help="Optional name to identify cmd in logs", type=str)
def main(
    global_options, input_file_options, input_url, output_file_options, output_url, name
):
    """Main function to process video files using FFmpeg with AWS
    integration."""
    aws_region = aws.detect_running_region()
    ssm_client, s3_client = configure_aws_clients(aws_region)

    # Log all parameters
    for param_name, value in locals().items():
        logging.info(f"{param_name}: {value}")

    # Convert "null" strings to None
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
    env_vars = {
        "AWS_BATCH_JOB_ID": os.getenv("AWS_BATCH_JOB_ID", "local"),
        "AWS_BATCH_JQ_NAME": os.getenv("AWS_BATCH_JQ_NAME", "local"),
        "AWS_BATCH_CE_NAME": os.getenv("AWS_BATCH_CE_NAME", "local"),
        "S3_BUCKET": os.getenv("S3_BUCKET"),
        "FSX_MOUNT_POINT": os.getenv("FSX_MOUNT_POINT"),
    }

    logging.info("Environment variables : %r", env_vars)

    # Start X-Ray segment
    xray_recorder.begin_segment("batch-ffmpeg-job")

    try:
        # Set X-Ray metadata and annotations
        segment = xray_recorder.current_segment()
        segment.put_metadata(
            "execution", f"ffmpeg-wrapper-{time.strftime('%Y%m%d-%H%M%S')}"
        )
        segment.put_annotation("application", "batch-ffmpeg")
        for key, value in {**locals(), **env_vars}.items():
            if key not in ["ssm_client", "s3_client", "env_vars", "segment"]:
                segment.put_annotation(key, str(value))

        input_files_path, output_file_path, tmp_dir = prepare_assets(
            input_url=input_url,
            output_url=output_url,
            s3_client=s3_client,
            fsx_lustre_mount_point=env_vars["FSX_MOUNT_POINT"],
        )

        if env_vars["AWS_BATCH_JQ_NAME"] == "batch-ffmpeg-job-queue-nvidia":
            nvidia_smi()

        command_list = create_ffmpeg_command(
            global_options,
            input_file_options,
            input_files_path,
            output_file_options,
            output_file_path,
        )
        execute_ffmpeg_command(command_list)
        # Upload output to S3 if not using FSx for Lustre
        if not env_vars["FSX_MOUNT_POINT"]:
            upload_to_s3(s3_client, output_file_path, output_url)

        # Calculate video quality metrics
        quality_metrics(
            input_files_path,
            output_file_path,
            output_url,
            env_vars,
            s3_client,
            ssm_client,
        )
        sys.exit(0)
    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        xray_recorder.current_segment().add_exception(e)
        sys.exit(1)
    finally:
        # Clean up the temporary directory if it was created
        if tmp_dir:
            tmp_dir.cleanup()
        # End X-Ray segment
        xray_recorder.end_segment()


if __name__ == "__main__":
    main()  # This actually runs the Click command
