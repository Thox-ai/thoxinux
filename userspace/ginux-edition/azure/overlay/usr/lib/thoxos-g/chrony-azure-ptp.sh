#!/bin/bash
# Copyright (c) 2026 THOX.ai LLC. Licensed under the Apache License, Version 2.0.
# Write the chrony refclock for the Hyper-V PTP clock when it exists.
# On Hyper-V (Azure) the device appears once hv_utils loads; wait briefly for
# udev. Anywhere else, remove the refclock so chronyd does not fail.
set -euo pipefail
dir=/run/thoxos-g/chrony
conf="$dir/azure-ptp.conf"
mkdir -p "$dir"
if [ -d /sys/bus/vmbus/devices ]; then
    for _ in $(seq 1 20); do
        [ -e /dev/ptp_hyperv ] && break
        sleep 0.25
    done
fi
if [ -e /dev/ptp_hyperv ]; then
    printf 'refclock PHC /dev/ptp_hyperv poll 3 dpoll -2 offset 0 stratum 2\n' > "$conf"
    echo "chrony: Hyper-V PTP refclock enabled"
else
    rm -f "$conf"
    echo "chrony: no /dev/ptp_hyperv, NTP pool only"
fi
