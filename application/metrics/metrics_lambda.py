# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
import logging
import os
from datetime import datetime
import json
import boto3

LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
logging.basicConfig(level=LOGLEVEL)
logger = logging.getLogger()
logger.setLevel(LOGLEVEL)

today = datetime.now()
midnight = datetime.combine(today, datetime.min.time())
day_hive_str = today.strftime("year=%Y/month=%b/day=%d")

s3_bucket = os.getenv("S3_BUCKET", None)

xray = boto3.client("xray")
s3 = boto3.client("s3")
glue = boto3.client("glue")


def save_s3(document):
    """Save document on Amazon S3 with specific key"""
    key = (
        "metrics/xray/"
        + day_hive_str
        + "/xray_segment_"
        + document["segment_id"]
        + ".json"
    )
    s3.put_object(Bucket=s3_bucket, Key=key, Body=json.dumps(document))
    logging.info("object %s saved", key)


def save_segment(trace):
    for segment in trace["Segments"]:
        result = json.loads(segment["Document"])
        result["segment_id"] = result.pop("id")
        result["trace_id"] = trace["trace_id"]
        save_s3(result)


def save_segments(batch_iterator):
    """Save XRAY segments on Amazon S3"""
    for batch in batch_iterator:
        for trace in batch["Traces"]:
            trace["trace_id"] = trace.pop("Id")
            save_segment(trace)


def export_handler(event, context):
    # Get Trace Summaries
    paginator = xray.get_paginator("get_trace_summaries")
    response_iterator = paginator.paginate(
        StartTime=midnight,
        EndTime=today,
        TimeRangeType="Event",
        Sampling=False,
        FilterExpression='annotation.application="ffmpeg-wrapper"',
    )

    # Collect Trace Ids
    trace_ids = []
    for page in response_iterator:
        if page["TraceSummaries"]:
            for trace_summary in page["TraceSummaries"]:
                trace_ids.append(trace_summary["Id"])
    logging.info("%s traces collected", len(trace_ids))
    # Get all traces and save segments
    composite_trace_ids = [trace_ids[x: x + 5] for x in range(0, len(trace_ids), 5)]
    paginator = xray.get_paginator("batch_get_traces")
    for ids in composite_trace_ids:
        response_iterator = paginator.paginate(
            TraceIds=ids,
        )
        save_segments(response_iterator)

    # Glue crawler
    try:
        glue.start_crawler(Name="aws_batch_ffmpeg_crawler")
    except glue.exceptions.CrawlerRunningException:
        logging.info("Crawler already running")

    return {
        "statusCode": 200,
        "body": json.dumps({"message": "{} traces exported".format(len(trace_ids))}),
    }


if __name__ == "__main__":
    event = []
    context = []
    export_handler(event, context)
