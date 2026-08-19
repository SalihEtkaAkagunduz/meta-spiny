#!/bin/sh
# Default ROS2 shell environment for SpinyOS targets.

SPINY_ROS_DISTRO="${SPINY_ROS_DISTRO:-humble}"

if [ -f "/opt/ros/${SPINY_ROS_DISTRO}/setup.sh" ]; then
    . "/opt/ros/${SPINY_ROS_DISTRO}/setup.sh"
elif [ -f "/opt/ros/${SPINY_ROS_DISTRO}/local_setup.sh" ]; then
    . "/opt/ros/${SPINY_ROS_DISTRO}/local_setup.sh"
fi

export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}"
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-0}"
export ROS_LOCALHOST_ONLY="${ROS_LOCALHOST_ONLY:-0}"
