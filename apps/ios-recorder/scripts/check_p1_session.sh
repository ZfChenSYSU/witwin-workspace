#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "用法: $0 /path/to/session_YYYYMMDD_HHMMSS" >&2
  exit 64
fi

session_dir=$1
if [[ ! -d "$session_dir" ]]; then
  echo "错误：session 目录不存在：$session_dir" >&2
  exit 66
fi

required_files=(
  metadata.json
  capabilities.json
  assembly.json
  rear_video.mov
  ar_frames.csv
  face_anchors.csv
  imu.csv
  events.csv
  validation_report.json
  checksums.sha256
)

for name in "${required_files[@]}"; do
  if [[ ! -s "$session_dir/$name" ]]; then
    echo "错误：缺少文件或文件为空：$name" >&2
    exit 65
  fi
done

awk -F, '
  NR == 1 {
    if (NF != 33) {
      print "错误：ar_frames.csv 表头列数不是 33" > "/dev/stderr"
      exit 1
    }
    next
  }
  {
    if (NF != 33) {
      print "错误：ar_frames.csv 第 " NR " 行列数错误" > "/dev/stderr"
      exit 1
    }
    if (count > 0 && $1 <= previous) {
      print "错误：ARFrame 时间戳不严格递增，行 " NR > "/dev/stderr"
      exit 1
    }
    previous = $1
    count += 1
    if ($5 == "true") {
      video += 1
    } else {
      dropped += 1
    }
  }
  END {
    if (count == 0) {
      print "错误：ar_frames.csv 没有数据" > "/dev/stderr"
      exit 1
    }
    printf "ARFrame=%d, video=%d, dropped=%d\n", count, video, dropped
  }
' "$session_dir/ar_frames.csv"

awk -F, '
  NR == 1 {
    if (NF != 8) {
      print "错误：imu.csv 表头列数不是 8" > "/dev/stderr"
      exit 1
    }
    next
  }
  {
    sensor = $3
    if (seen[sensor] && $1 <= previous[sensor]) {
      print "错误：IMU/" sensor " 时间戳不严格递增，行 " NR > "/dev/stderr"
      exit 1
    }
    seen[sensor] = 1
    previous[sensor] = $1
    counts[sensor] += 1
    total += 1
  }
  END {
    if (total == 0) {
      print "错误：imu.csv 没有数据" > "/dev/stderr"
      exit 1
    }
    printf "IMU samples=%d\n", total
    for (sensor in counts) {
      printf "  %s=%d\n", sensor, counts[sensor]
    }
  }
' "$session_dir/imu.csv"

if ! awk -F, 'NR > 1 && $3 == "session_started" { started=1 }
               NR > 1 && $3 == "session_stopped" { stopped=1 }
               END { exit !(started && stopped) }' "$session_dir/events.csv"; then
  echo "错误：events.csv 缺少 session_started 或 session_stopped" >&2
  exit 1
fi

(
  cd "$session_dir"
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 -c checksums.sha256
  elif command -v sha256sum >/dev/null 2>&1; then
    sha256sum -c checksums.sha256
  else
    echo "错误：找不到 shasum 或 sha256sum" >&2
    exit 69
  fi
)

if command -v jq >/dev/null 2>&1; then
  jq '{
    passed,
    errors,
    warnings,
    statistics
  }' "$session_dir/validation_report.json"
fi

echo "P1 session 离线完整性检查通过：$session_dir"
