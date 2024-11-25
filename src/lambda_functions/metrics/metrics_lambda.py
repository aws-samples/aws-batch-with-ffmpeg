"""X-Ray Trace Export and Analysis Script.

This script exports X-Ray traces from AWS, processes them, and updates related
Athena views. It includes functionality to interact with various AWS services
including X-Ray, S3, Glue, and Athena.

The script performs the following main operations:
1. Retrieves X-Ray trace summaries
2. Processes and saves trace segments to S3
3. Triggers and waits for a Glue crawler to run
4. Updates Athena views based on the processed data

Usage:
    This script is designed to be run as an AWS Lambda function, but can also
    be executed standalone for testing purposes.
"""

import glob
import json
import logging
import os
import time
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional

import boto3

# Constants
LOGLEVEL: str = os.environ.get("LOGLEVEL", "INFO").upper()
S3_BUCKET: str = os.environ.get("S3_BUCKET", "gma-test")
ATHENA_RESULT_LOCATION: str = f"s3://{S3_BUCKET}/athena/queries/"
CRAWLER_NAME: str = "batch_ffmpeg_crawler"
MAX_WORKERS: int = 10  # Adjust based on your Lambda function's resources

# Setup logging
LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
logging.basicConfig(level=LOGLEVEL)
logger = logging.getLogger()
logger.setLevel(LOGLEVEL)

# Initialize AWS clients
s3: Any = boto3.client("s3")
xray: Any = boto3.client("xray")
glue: Any = boto3.client("glue")
athena: Any = boto3.client("athena")


def get_hive_partition() -> str:
    """Generate the Hive-style partition string for the current date.

    Returns:
        str: A string in the format "year=YYYY/month=MMM/day=DD"
    """
    today: datetime = datetime.now(tz=timezone.utc)
    return today.strftime("year=%Y/month=%b/day=%d")


def normalize_subsegment(subsegment: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a subsegment to ensure consistent field ordering.

    Args:
        subsegment (Dict[str, Any]): The subsegment dictionary to normalize

    Returns:
        Dict[str, Any]: A new dictionary with fields in the correct order
    """
    # Create new dict with fields in specific order matching table schema
    return {
        "id": subsegment.get("id"),
        "name": subsegment.get("name"),
        "start_time": subsegment.get("start_time"),
        "end_time": subsegment.get("end_time"),
        "in_progress": subsegment.get("in_progress", False),
        "namespace": subsegment.get(
            "namespace"
        ),  # namespace before metadata to match table schema
        "metadata": subsegment.get("metadata", {}),
    }


def normalize_subsegments(document: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize all subsegments in a document to ensure consistent field ordering.

    Args:
        document (Dict[str, Any]): The document containing subsegments

    Returns:
        Dict[str, Any]: The document with normalized subsegments
    """
    if "subsegments" in document:
        document["subsegments"] = [
            normalize_subsegment(subseg) for subseg in document["subsegments"]
        ]
    return document


def save_segment(trace: Dict[str, Any]) -> None:
    """Save individual segments from a trace to S3.

    Args:
        trace (Dict[str, Any]): A dictionary containing trace data, including segments.
    """
    for segment in trace["Segments"]:
        document: Dict[str, Any] = json.loads(segment["Document"])
        # Rename 'id' to 'segment_id' and add 'trace_id'
        document["segment_id"] = document.pop("id")
        document["trace_id"] = trace["trace_id"]

        # Normalize subsegments to ensure consistent field ordering
        document = normalize_subsegments(document)

        # Generate S3 key and save the document
        key: str = f"metrics/xray/{get_hive_partition()}/xray_segment_{document['segment_id']}.json"
        s3.put_object(Bucket=S3_BUCKET, Key=key, Body=json.dumps(document))


def process_trace_batch(batch: Dict[str, Any]) -> None:
    """Process a batch of traces, saving their segments to S3.

    Args:
        batch (Dict[str, Any]): A dictionary containing a batch of traces.
    """
    for trace in batch["Traces"]:
        trace["trace_id"] = trace.pop("Id")
        save_segment(trace)


def get_trace_ids() -> List[str]:
    """Retrieve trace IDs from X-Ray for the current day.

    Returns:
        List[str]: A sorted list of unique trace IDs.
    """
    paginator: Any = xray.get_paginator("get_trace_summaries")
    today: datetime = datetime.now(tz=timezone.utc)
    midnight: datetime = datetime.combine(today, datetime.min.time())

    trace_ids: List[str] = []
    for page in paginator.paginate(
        StartTime=midnight,
        EndTime=today,
        TimeRangeType="Event",
        Sampling=False,
        FilterExpression='annotation.application="batch-ffmpeg"',
    ):
        trace_ids.extend([summary["Id"] for summary in page["TraceSummaries"]])

    return sorted(set(trace_ids))


def process_traces(trace_ids: List[str]) -> None:
    """Process traces in parallel using a ThreadPoolExecutor.

    Args:
        trace_ids (List[str]): A list of trace IDs to process.
    """
    paginator: Any = xray.get_paginator("batch_get_traces")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures: List[Any] = []
        for i in range(0, len(trace_ids), 5):
            batch_ids: List[str] = trace_ids[i : i + 5]
            for batch in paginator.paginate(TraceIds=batch_ids):
                futures.append(executor.submit(process_trace_batch, batch))

        # Wait for all futures to complete, raising any exceptions
        for future in as_completed(futures):
            future.result()


def run_athena_query(query: str) -> None:
    """Execute an Athena query and wait for its completion.

    Args:
        query (str): The SQL query to execute.

    Raises:
        ClientError: If the query fails to execute successfully.
    """
    response: Dict[str, Any] = athena.start_query_execution(
        QueryString=query,
        ResultConfiguration={"OutputLocation": ATHENA_RESULT_LOCATION},
    )
    query_execution_id: str = response["QueryExecutionId"]

    # Poll for query completion
    while True:
        query_execution: Dict[str, Any] = athena.get_query_execution(
            QueryExecutionId=query_execution_id
        )
        status: str = query_execution["QueryExecution"]["Status"]["State"]
        if status in ["SUCCEEDED", "FAILED", "CANCELLED"]:
            break
        time.sleep(1)

    if status != "SUCCEEDED":
        error_message = query_execution["QueryExecution"]["Status"].get(
            "StateChangeReason", "Unknown reason"
        )
        raise Exception(f"Query failed: {error_message}")


def update_athena_views() -> None:
    """Update Athena views by executing DDL statements from files."""
    ddl_files: List[str] = glob.glob(
        os.path.join(os.path.dirname(__file__), "athena_ddl", "*.ddl")
    )

    for ddl_file in ddl_files:
        with open(ddl_file) as ddl:
            logger.info(f"Running Athena query from {ddl_file}")
            run_athena_query(ddl.read())


def wait_for_crawler(timeout_minutes: int = 120, retry_seconds: int = 5) -> None:
    """Wait for the Glue crawler to complete its run.

    Args:
        timeout_minutes (int): Maximum time to wait for the crawler.
        retry_seconds (int): Time to wait between status checks.

    Raises:
        TimeoutError: If the crawler doesn't complete within the specified timeout.
    """
    start_time: float = time.time()
    timeout: float = start_time + (timeout_minutes * 60)
    state_previous: Optional[str] = None

    while time.time() < timeout:
        response: Dict[str, Any] = glue.get_crawler(Name=CRAWLER_NAME)
        state: str = response["Crawler"]["State"]

        if state != state_previous:
            logger.info(f"Crawler {CRAWLER_NAME} is {state.lower()}")
            state_previous = state

        if state == "READY":
            return

        time.sleep(retry_seconds)

    raise TimeoutError(
        f"Crawler {CRAWLER_NAME} did not complete within {timeout_minutes} minutes"
    )


def export_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main Lambda handler function for exporting and processing X-Ray traces.

    Args:
        event (Dict[str, Any]): The event dict containing the Lambda function parameters.
        context (Any): The context in which the Lambda function is running.

    Returns:
        Dict[str, Any]: A dictionary containing the status code and result message.
    """
    try:
        logger.info("Starting X-Ray trace export")

        # Step 1: Retrieve trace IDs
        trace_ids: List[str] = get_trace_ids()
        logger.info(f"{len(trace_ids)} traces collected")

        # Step 2: Process traces and save segments to S3
        process_traces(trace_ids)

        # Step 3: Start the Glue crawler
        try:
            glue.start_crawler(Name=CRAWLER_NAME)
            logger.info(f"Started Glue crawler {CRAWLER_NAME}")
        except glue.exceptions.CrawlerRunningException:
            logger.info(f"Glue crawler {CRAWLER_NAME} is already running")

        # Step 4: Wait for the crawler to complete
        wait_for_crawler()

        # Step 5: Update Athena views
        logger.info("Updating Athena views")
        update_athena_views()

        return {
            "statusCode": 200,
            "body": json.dumps({"message": f"{len(trace_ids)} traces exported"}),
        }
    except Exception as e:
        logger.error(f"Error during export: {str(e)}", exc_info=True)
        return {"statusCode": 500, "body": json.dumps({"message": str(e)})}


if __name__ == "__main__":
    # For local testing
    export_handler({}, None)
