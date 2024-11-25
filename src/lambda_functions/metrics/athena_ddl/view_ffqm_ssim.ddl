CREATE OR REPLACE VIEW batch_ffmpeg.batch_ffmpeg_ffqm_ssim AS
SELECT
    aws_batch_job_id,
    aws_batch_jq_name,
    aws_batch_ce_name,
    ssim_array.n as n,
    ssim_array.ssim_y as ssim_y,
    ssim_array.ssim_u as ssim_u,
    ssim_array.ssim_v as ssim_v,
    ssim_array.ssim_avg as ssim_avg
FROM batch_ffmpeg.batch_ffmpeg_ffqm
CROSS JOIN UNNEST(batch_ffmpeg.batch_ffmpeg_ffqm.ssim) AS t(ssim_array)
