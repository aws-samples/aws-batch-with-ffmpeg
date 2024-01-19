# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
import glob
import json
import logging
import os
import time
import timeit
from datetime import datetime, timezone

import boto3

LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
logging.basicConfig(level=LOGLEVEL)
logger = logging.getLogger()
logger.setLevel(LOGLEVEL)

today = datetime.now(tz=timezone.utc)
midnight = datetime.combine(today, datetime.min.time())
day_hive_str = today.strftime("year=%Y/month=%b/day=%d")

s3_bucket = os.getenv("S3_BUCKET", "gma-test")
athena_result_location = "s3://" + s3_bucket + "/athena/queries/"
xray = boto3.client("xray")
s3 = boto3.client("s3")
glue = boto3.client("glue")
athena = boto3.client("athena")


def save_s3(document):
    """Save document on Amazon S3 with specific key."""
    key = (
        "metrics/xray/"
        + day_hive_str
        + "/xray_segment_"
        + document["segment_id"]
        + ".json"
    )
    s3.put_object(Bucket=s3_bucket, Key=key, Body=json.dumps(document))


def save_segment(trace):
    for segment in trace["Segments"]:
        result = json.loads(segment["Document"])
        result["segment_id"] = result.pop("id")
        result["trace_id"] = trace["trace_id"]
        save_s3(result)


def save_segments(batch_iterator):
    """Save XRAY segments on Amazon S3."""
    for batch in batch_iterator:
        for trace in batch["Traces"]:
            trace["trace_id"] = trace.pop("Id")
            save_segment(trace)


def update_athena_views():
    """Create or update athena views after Glue Crawler stopped."""
    ddl_files = glob.glob(os.path.dirname(__file__) + "/athena_ddl/*.ddl")

    for ddl_file in ddl_files:
        with open(ddl_file) as ddl:
            logging.info("Running athena query of %s", ddl_file)
            response = athena.start_query_execution(
                QueryString=ddl.read(),
                ResultConfiguration={"OutputLocation": athena_result_location},
            )
            logging.info(
                "Running athena query of %s : Query execution Id = %s",
                ddl_file,
                response["QueryExecutionId"],
            )


def wait_crawler_running(
    crawler_name: str, timeout_minutes: int = 120, retry_seconds: int = 5
):
    """Wait crawler stopping."""
    timeout_seconds = timeout_minutes * 60
    client = boto3.client("glue")
    start_time = timeit.default_timer()
    abort_time = start_time + timeout_seconds
    state_previous = None
    while True:
        response_get = client.get_crawler(Name=crawler_name)
        state = response_get["Crawler"]["State"]
        if state != state_previous:
            logging.info("Crawler %s is %s", crawler_name, state.lower())
            state_previous = state
        if state == "READY":  # Other known states: RUNNING, STOPPING
            return
        if timeit.default_timer() > abort_time:
            raise TimeoutError(
                f"Failed to crawl {crawler_name}. The allocated time of {timeout_minutes:,} minutes has elapsed."
            )
        time.sleep(retry_seconds)


def export_handler(event, context):
    """Lambda handler."""
    logging.info("Get Xray Trace Summaries")
    # Get Trace Summaries
    paginator = xray.get_paginator("get_trace_summaries")
    response_iterator = paginator.paginate(
        StartTime=midnight,
        EndTime=today,
        TimeRangeType="Event",
        Sampling=False,
        FilterExpression='annotation.application="batch-ffmpeg"',
    )

    # Collect Trace Ids
    trace_ids = []
    for page in response_iterator:
        if page["TraceSummaries"]:
            for trace_summary in page["TraceSummaries"]:
                trace_ids.append(trace_summary["Id"])
    logging.info("%s traces collected", len(trace_ids))

    # Get all traces and save segments
    trace_ids = sorted(set(trace_ids))
    composite_trace_ids = [trace_ids[x : x + 5] for x in range(0, len(trace_ids), 5)]
    paginator = xray.get_paginator("batch_get_traces")
    for ids in composite_trace_ids:
        response_iterator = paginator.paginate(
            TraceIds=ids,
        )
        save_segments(response_iterator)

    # Glue crawler
    crawler_name = "aws_batch_ffmpeg_crawler"
    try:
        glue.start_crawler(Name=crawler_name)
        logging.info("Starting Glue crawler")
    except glue.exceptions.CrawlerRunningException:
        logging.info("Glue crawler is %s already running", crawler_name)

    # Wait Crawler
    wait_crawler_running(crawler_name=crawler_name)
    logging.info("Updating Athena views")
    # Update Athena views
    update_athena_views()
    return {
        "statusCode": 200,
        "body": json.dumps({"message": f"{len(trace_ids)} traces exported"}),
    }


if __name__ == "__main__":
    event = []
    context = []
    export_handler(event, context)
