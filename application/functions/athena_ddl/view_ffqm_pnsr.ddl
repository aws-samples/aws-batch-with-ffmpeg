CREATE OR REPLACE VIEW aws_batch_ffmpeg.batch_ffmpeg_ffqm_psnr AS
SELECT
    aws_batch_job_id,
    aws_batch_jq_name,
    aws_batch_ce_name,
    psnr_array.n as n,
    psnr_array.mse_avg as mse_avg,
    psnr_array.mse_y as mse_y,
    psnr_array.mse_u as mse_u,
    psnr_array.mse_v as mse_v,
    psnr_array.psnr_avg as psnr_avg,
    psnr_array.psnr_y as psnr_y,
    psnr_array.psnr_u as psnr_u,
    psnr_array.psnr_v as psnr_v
FROM aws_batch_ffmpeg.batch_ffmpeg_ffqm
CROSS JOIN UNNEST(aws_batch_ffmpeg.batch_ffmpeg_ffqm.psnr) AS t(psnr_array)
