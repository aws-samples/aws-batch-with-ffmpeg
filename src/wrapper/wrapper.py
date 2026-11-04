import errno
import json
import logging
import os
import re
import shlex
import subprocess  # nosec B404
import sys
import tempfile
import time
import traceback
from typing import List, Tuple

import boto3
import click
from aws_xray_sdk.core import xray_recorder
from botocore.exceptions import ClientError

from shared_libraries import aws
from shared_libraries import aws_s3
from shared_libraries import s3_posix
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
    input_url: str, output_url: str, s3files_mount_point: str, s3_client
) -> Tuple[List[str], str, tempfile.TemporaryDirectory]:
    """Prepare media assets by downloading from S3 url to local storage or
    translate urls from S3 to Amazon S3 Files path."""
    s3_output_url = S3Url(output_url)
    s3_inputs = input_url.replace(" ", "").split(",")

    if not s3files_mount_point:
        # Create a temporary directory for S3 downloads
        logging.info(
            "No Amazon S3 Files mount point provided, using temporary directory"
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
        # Use Amazon S3 Files
        logging.info("Using Amazon S3 Files mount point")
        tmp_dir = None
        output_file_path = os.path.join(s3files_mount_point, s3_output_url.key)
        logging.info(f"Output file path: {output_file_path}")
        input_files_path = []
        for s3_input in s3_inputs:
            s3_input_url = S3Url(s3_input)
            input_file_path = os.path.join(s3files_mount_point, s3_input_url.key)
            if not os.path.isfile(input_file_path):
                logging.error(f"File {input_file_path} not found on Amazon S3 Files")
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


class UnsafeFfmpegOptionError(ValueError):
    """A user supplied ffmpeg option was rejected by the allowlist."""


# ffmpeg protocols the job legitimately needs. The wrapper always hands ffmpeg
# local paths: inputs are either downloaded from S3 into a temp directory or
# read from the Amazon S3 Files mount point, and the output is a local path too.
# So only local protocols are allowed, which blocks the network protocols
# (http, tcp, ...) that turn a crafted option or input into SSRF or data
# exfiltration, and the indirection protocols (concat, subfile) that reach
# other resources. The value is applied per input in create_ffmpeg_command.
FFMPEG_PROTOCOL_WHITELIST = "file,crypto,data,pipe"

# Rejected in any user supplied option token. The protocol prefixes map a token
# onto a network or indirection protocol regardless of -protocol_whitelist
# (which only guards -i inputs); the flags let an option field reach a resource
# or smuggle an input past the whitelist that is attached to the managed -i.
_FORBIDDEN_OPTION_SUBSTRINGS = (
    "http://",
    "https://",
    "ftp://",
    "ftps://",
    "tcp://",
    "udp://",
    "rtp://",
    "rtmp://",
    "rtmps://",
    "rtsp://",
    "srt://",
    "sftp://",
    "ssh://",
    "gopher://",
    "telnet://",
    "file:",
    "concat:",
    "subfile:",
    "data:",
    "pipe:",
    "async:",
    "cache:",
)
# The only ffmpeg flags a caller may pass, keyed by their base name (the part
# before an optional :stream_specifier). A flag absent from these sets is
# rejected, so a flag that names a file (-vstats_file, -passlogfile,
# -filter_script, -sdp_file, -progress, ...) never reaches ffmpeg. Flags in the
# first set take no value; every other allowed flag consumes the next token.
_BOOLEAN_FLAGS = frozenset(
    {
        "an",
        "vn",
        "sn",
        "dn",
        "y",
        "n",
        "shortest",
        "hide_banner",
        "nostdin",
        "stats",
        "nostats",
        "copyts",
        "start_at_zero",
        "re",
    }
)
_VALUED_FLAGS = frozenset(
    {
        # codecs and encoder tuning
        "c",
        "codec",
        "vcodec",
        "acodec",
        "scodec",
        "preset",
        "tune",
        "profile",
        "level",
        "crf",
        "cq",
        "qp",
        "q",
        "qscale",
        "b",
        "ab",
        "maxrate",
        "minrate",
        "bufsize",
        "g",
        "keyint_min",
        "sc_threshold",
        "bf",
        "refs",
        "rc",
        "pix_fmt",
        "x264-params",
        "x265-params",
        "vtag",
        "tag",
        "strict",
        "threads",
        # geometry, rate and audio layout
        "s",
        "r",
        "aspect",
        "ar",
        "ac",
        "sample_fmt",
        "channel_layout",
        "fps_mode",
        "vsync",
        # timing and selection
        "ss",
        "sseof",
        "t",
        "to",
        "frames",
        "vframes",
        "aframes",
        "map",
        "map_metadata",
        "map_chapters",
        "metadata",
        "disposition",
        "start_number",
        "max_muxing_queue_size",
        # container, muxer and logging
        "f",
        "movflags",
        "segment_time",
        "hls_time",
        "hls_list_size",
        "loglevel",
        "v",
        # hardware decode and scaling (GPU job definitions)
        "hwaccel",
        "hwaccel_output_format",
        "hwaccel_device",
        "resize",
        "extra_hw_frames",
        # filters, checked separately as a filter graph
        "vf",
        "af",
        "filter",
        "filter_complex",
        "lavfi",
    }
)
_FILTERGRAPH_FLAGS = frozenset({"vf", "af", "filter", "filter_complex", "lavfi"})

# Formats accepted by -f. Demuxers that read other resources from their own
# content (concat, lavfi, image2pipe, the devices) are absent on purpose.
_ALLOWED_FORMATS = frozenset(
    {
        "mp4",
        "mov",
        "matroska",
        "webm",
        "mpegts",
        "mp3",
        "adts",
        "aac",
        "wav",
        "flac",
        "ogg",
        "opus",
        "image2",
        "gif",
        "null",
        "hls",
        "dash",
        "segment",
        "ipod",
        "ismv",
        "mxf",
        "rawvideo",
    }
)

# Filters accepted in a filter graph. Every one of them only transforms the
# frames it is given: the source filters that open a file or a URL themselves
# (movie, amovie), the ones that load a file or a plugin (subtitles, ass,
# lut3d, frei0r, ladspa, lv2, sendcmd, zmq, the dnn filters) and the ones that
# write side files (vidstab, signature, psnr/ssim stats) are absent on purpose.
_ALLOWED_FILTERS = frozenset(
    {
        "scale",
        "scale_npp",
        "scale_cuda",
        "fps",
        "framerate",
        "crop",
        "pad",
        "setsar",
        "setdar",
        "format",
        "transpose",
        "hflip",
        "vflip",
        "rotate",
        "trim",
        "atrim",
        "setpts",
        "asetpts",
        "tpad",
        "apad",
        "concat",
        "overlay",
        "split",
        "asplit",
        "hstack",
        "vstack",
        "xstack",
        "xfade",
        "acrossfade",
        "amix",
        "amerge",
        "pan",
        "channelmap",
        "volume",
        "aresample",
        "aformat",
        "atempo",
        "loudnorm",
        "dynaudnorm",
        "yadif",
        "bwdif",
        "fade",
        "afade",
        "null",
        "anull",
        "hwupload",
        "hwdownload",
        "hwupload_cuda",
        "thumbnail",
        "select",
        "aselect",
        "tile",
        "palettegen",
        "paletteuse",
        "colorspace",
        "zscale",
        "unsharp",
        "boxblur",
        "gblur",
        "eq",
        "hue",
        "drawbox",
        "drawtext",
        "hqdn3d",
        "deblock",
        "chromakey",
        "colorkey",
        "alphamerge",
        "showwaves",
    }
)
# Filter arguments that make an otherwise allowed filter read a file whose
# content ends up in the output. drawtext fontfile only selects glyph shapes
# and stays allowed.
_FORBIDDEN_FILTER_ARGUMENTS = ("textfile",)
_FILTER_LABELS = re.compile(r"^\s*(\[[^\]]*\]\s*)*")
_FILTER_NAME = re.compile(r"^[A-Za-z0-9_]+")
_NUMBER = re.compile(r"^-?\d+(\.\d+)?$")


def _validate_filtergraph(label: str, graph: str) -> None:
    """Reject a filter graph naming a filter outside the allowlist.

    The graph is split on every ',' and ';', including escaped or quoted ones.
    That yields a superset of ffmpeg's own filter boundaries, so every filter
    ffmpeg would instantiate is checked, and a fragment of quoted text that does
    not start with an allowed filter name fails closed.
    """
    lowered = graph.lower()
    for argument in _FORBIDDEN_FILTER_ARGUMENTS:
        if argument in lowered:
            raise UnsafeFfmpegOptionError(
                f"{label}: the filter argument {argument!r} is not allowed"
            )
    for segment in re.split(r"[,;]", graph):
        body = _FILTER_LABELS.sub("", segment, count=1).strip()
        if not body:
            continue
        match = _FILTER_NAME.match(body)
        name = match.group(0).lower() if match else body
        if name not in _ALLOWED_FILTERS:
            raise UnsafeFfmpegOptionError(
                f"{label}: the filter {name!r} is not allowed in {label}"
            )


def validate_ffmpeg_options(label: str, options: str) -> None:
    """Accept a user supplied ffmpeg option string only if every token is an
    allowed flag or the value of one.

    The three option fields (global_options, input_file_options,
    output_file_options) are free text controlled by the API caller and are
    spliced into the ffmpeg argv, where ffmpeg's own flags, demuxers and filter
    sources turn them into arbitrary file read/write and SSRF. Only allowlisted
    flags, -f formats and filters are accepted, and no token may stand alone, so
    a caller cannot add an input, an output or a side file. This runs at the
    only point the client cannot bypass, before the command is built.

    Args:
        label: The name of the option field, used in the error message.
        options: The raw option string, or a falsy value when absent.

    Raises:
        UnsafeFfmpegOptionError: A token is outside the allowlist.
    """
    if not options:
        return
    tokens = shlex.split(options)
    for token in tokens:
        lowered = token.lower()
        for forbidden in _FORBIDDEN_OPTION_SUBSTRINGS:
            if forbidden in lowered:
                raise UnsafeFfmpegOptionError(
                    f"{label}: token {token!r} contains the forbidden "
                    f"protocol prefix {forbidden!r}"
                )

    index = 0
    while index < len(tokens):
        token = tokens[index]
        if not token.startswith("-") or _NUMBER.match(token):
            # A bare token is an extra input or output path to ffmpeg.
            raise UnsafeFfmpegOptionError(
                f"{label}: the token {token!r} is not an allowed option"
            )
        # ffmpeg flags accept a :stream_specifier suffix (e.g. -c:v).
        flag = token[1:].split(":", 1)[0].lower()
        if flag in _BOOLEAN_FLAGS:
            index += 1
            continue
        if flag not in _VALUED_FLAGS:
            raise UnsafeFfmpegOptionError(
                f"{label}: the option {token!r} is not allowed in {label}"
            )
        if index + 1 >= len(tokens):
            raise UnsafeFfmpegOptionError(f"{label}: the option {token!r} has no value")
        value = tokens[index + 1]
        if flag in _FILTERGRAPH_FLAGS:
            _validate_filtergraph(label, value)
        elif flag == "f" and value.lower() not in _ALLOWED_FORMATS:
            raise UnsafeFfmpegOptionError(
                f"{label}: the format {value!r} is not allowed in {label}"
            )
        index += 2


def create_ffmpeg_command(
    global_options,
    input_file_options,
    input_files_path,
    output_file_options,
    output_file_path,
):
    """Create the FFmpeg command list based on the provided options and file
    paths.

    The three option fields are validated first and the protocol whitelist is
    applied per input, so a crafted option or input cannot make ffmpeg reach a
    network or indirection protocol.

    Raises:
        UnsafeFfmpegOptionError: A user supplied option was rejected.
    """
    validate_ffmpeg_options("global_options", global_options)
    validate_ffmpeg_options("input_file_options", input_file_options)
    validate_ffmpeg_options("output_file_options", output_file_options)

    command_list = ["ffmpeg"]
    if global_options:
        command_list.extend(shlex.split(global_options))
    if input_files_path:
        if input_file_options:
            command_list.extend(shlex.split(input_file_options))
        for file in input_files_path:
            # -protocol_whitelist is an input option reset between inputs, so it
            # is repeated before each -i to bound every input to local
            # protocols only.
            command_list.extend(
                ["-protocol_whitelist", FFMPEG_PROTOCOL_WHITELIST, "-i", file]
            )
    if output_file_path:
        if output_file_options:
            command_list.extend(shlex.split(output_file_options))
        command_list.append(output_file_path)
    return command_list


def upload_to_s3(s3_client, output_file_path, output_url):
    """Upload the output file or directory to S3."""
    s3_output_url = S3Url(output_url)
    try:
        # An object written with the S3 API only implies its parent directories,
        # and Amazon S3 Files presents an implied directory as root:root, which
        # the uid of the containers cannot write in. Materializing them here is
        # what lets a job that mounts this prefix later create its own output
        # directory, without any manual metadata fix on the bucket.
        s3_posix.ensure_object_directories(
            s3_client, s3_output_url.bucket, s3_output_url.key
        )
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
    # The metrics tree is written with the S3 API in both modes, so it needs the
    # same directory objects as the outputs : a job mounting the file system must
    # be able to write its own metrics file next to the ones already there.
    s3_posix.ensure_object_directories(s3_client, s3_bucket, key)
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
        "S3FILES_MOUNT_POINT": os.getenv("S3FILES_MOUNT_POINT"),
    }

    logging.info("Environment variables : %r", env_vars)

    # Temporary directory is only created by prepare_assets when S3 is used. It is
    # initialized here so the finally block can always safely inspect it, even if
    # prepare_assets raises before returning.
    tmp_dir = None

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
            if key not in ["ssm_client", "s3_client", "env_vars", "segment", "tmp_dir"]:
                segment.put_annotation(key, str(value))

        input_files_path, output_file_path, tmp_dir = prepare_assets(
            input_url=input_url,
            output_url=output_url,
            s3_client=s3_client,
            s3files_mount_point=env_vars["S3FILES_MOUNT_POINT"],
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
        # Upload output to S3 if not using Amazon S3 Files
        if not env_vars["S3FILES_MOUNT_POINT"]:
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
        # X-Ray instrumentation is best effort : a telemetry failure must never
        # hide or replace the business error reported above.
        try:
            segment = xray_recorder.current_segment()
            if segment:
                # Entity.add_exception(exception, stack, remote=False) : stack is a
                # traceback.extract_stack() formatted stack trace.
                segment.add_exception(e, traceback.extract_tb(e.__traceback__))
        except Exception as instrumentation_error:
            logging.warning(
                f"Unable to record the exception in X-Ray: {instrumentation_error!r}"
            )
        sys.exit(1)
    finally:
        # Clean up the temporary directory if it was created
        if tmp_dir:
            tmp_dir.cleanup()
        # End X-Ray segment
        xray_recorder.end_segment()


if __name__ == "__main__":
    main()  # This actually runs the Click command
