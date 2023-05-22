CREATE OR REPLACE VIEW aws_batch_ffmpeg.batch_ffmpeg_xray_subsegment AS
SELECT
    trace_id,
    subsegment.id as subsegement_id,
    annotations.name,
    subsegment.name as subsegment_name,
    CAST(from_unixtime(start_time) AS timestamp) as start_date,
    CAST(from_unixtime(end_time) AS timestamp) as end_date,
    CAST(from_unixtime(subsegment.start_time) AS timestamp) as subsegement_start_date,
    CAST(from_unixtime(subsegment.end_time) AS timestamp) as subsegement_end_date,
    date_diff('second',CAST(from_unixtime(start_time) AS timestamp),
    CAST(from_unixtime(end_time) AS timestamp)) trace_duration_sec,
    date_diff('second',CAST(from_unixtime(subsegment.start_time) AS timestamp),
    CAST(from_unixtime(subsegment.end_time) AS timestamp)) subsegment_duration_sec,
    aws.ec2.instance_type,
    annotations.aws_batch_jq_name
FROM aws_batch_ffmpeg.batch_ffmpeg_xray
CROSS JOIN UNNEST(aws_batch_ffmpeg.batch_ffmpeg_xray.subsegments) AS t(subsegment)
