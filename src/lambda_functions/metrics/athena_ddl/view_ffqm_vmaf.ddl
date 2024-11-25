CREATE OR REPLACE VIEW batch_ffmpeg.batch_ffmpeg_ffqm_vmaf AS
SELECT
    aws_batch_job_id,
    aws_batch_jq_name,
    aws_batch_ce_name,
    vmaf_array.integer_adm2 as avmaf_dm2,
    vmaf_array.integer_adm_scale0 as vmaf_adm_scale0,
    vmaf_array.integer_adm_scale1 as vmaf_adm_scale1,
    vmaf_array.integer_adm_scale2 as vmaf_adm_scale2,
    vmaf_array.integer_adm_scale3 as vmaf_adm_scale3,
    vmaf_array.integer_motion as vmaf_motion,
    vmaf_array.integer_motion2 as vmaf_motion2,
    vmaf_array.integer_vif_scale0 as vmaf_vif_scale0,
    vmaf_array.integer_vif_scale1 as vmaf_vif_scale1,
    vmaf_array.integer_vif_scale2 as vmaf_vif_scale2,
    vmaf_array.integer_vif_scale3 as vmaf_vif_scale3,
    vmaf_array.vmaf as vmaf
FROM batch_ffmpeg.batch_ffmpeg_ffqm
CROSS JOIN UNNEST(batch_ffmpeg.batch_ffmpeg_ffqm.vmaf) AS t(vmaf_array)
