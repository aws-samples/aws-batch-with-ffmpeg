#!/bin/bash
# Trigger an error if non-zero exit code is encountered
set -e

echo "*** Xilinx XRT setup"
source /opt/xilinx/xrt/setup.sh
echo "*** Xilinx XRMD start"
source /opt/xilinx/xcdr/xrmd_start.bash | true
echo "*** Xilinx XRM load devices"
xrmadm /opt/xilinx/xcdr/scripts/xrm_commands/load_multiple_devices/load_all_devices_cmd.json
echo "*** Xilinx XRM load plugins"
xrmadm /opt/xilinx/xcdr/scripts/xrm_commands/load_multi_u30_xrm_plugins_cmd.json
echo "*** Xilinx xbutil examine"
xbutil examine
echo "*** Python wrapper execution"
export LOGLEVEL='INFO'
python3 ffmpeg_wrapper.py "$@"
