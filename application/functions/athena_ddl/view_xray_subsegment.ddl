CREATE OR REPLACE VIEW aws_batch_ffmpeg.batch_ffmpeg_xray_subsegment AS
SELECT
    trace_id,
    subsegment.id as subsegement_id,
    annotations.name,
    subsegment.name as subsegment_name,
    start_time,
    end_time,
    subsegment."start_time" as subsegment_start_time,
    subsegment."end_time" as subsegment_end_time,
    CAST(from_unixtime(CAST(start_time as integer)) as timestamp) as start_date,
    CAST(from_unixtime(CAST(end_time as integer)) as timestamp) as end_date,
    CAST(from_unixtime(CAST(subsegment.start_time as integer)) as timestamp) as subsegment_start_date,
    CAST(from_unixtime(CAST(subsegment.end_time as integer)) as timestamp) as subsegment_end_date,
    date_diff('second',CAST(from_unixtime(start_time) AS timestamp), CAST(from_unixtime(end_time) AS timestamp)) trace_duration_sec,
    date_diff('second',CAST(from_unixtime(subsegment.start_time) AS timestamp), CAST(from_unixtime(subsegment.end_time) AS timestamp)) subsegment_duration_sec,
    aws.ec2.instance_type,
    annotations.aws_batch_jq_name
FROM aws_batch_ffmpeg.batch_ffmpeg_xray
CROSS JOIN UNNEST(aws_batch_ffmpeg.batch_ffmpeg_xray.subsegments) AS t(subsegment)
