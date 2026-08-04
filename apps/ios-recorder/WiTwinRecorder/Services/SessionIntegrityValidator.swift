import Foundation

enum SessionIntegrityValidator {
    static let requiredFiles = [
        "metadata.json",
        "capabilities.json",
        "assembly.json",
        "rear_video.mov",
        "ar_frames.csv",
        "face_anchors.csv",
        "imu.csv",
        "events.csv"
    ]

    static func validate(
        sessionID: String,
        directory: URL
    ) throws -> SessionValidationReport {
        var errors: [String] = []
        var warnings: [String] = []
        let fileManager = FileManager.default

        for name in requiredFiles {
            let url = directory.appendingPathComponent(name)
            guard fileManager.fileExists(atPath: url.path) else {
                errors.append("缺少必需文件：\(name)")
                continue
            }
            if fileSize(url) == 0 {
                errors.append("文件为空：\(name)")
            }
        }

        let ar = try inspectARFrames(
            directory.appendingPathComponent("ar_frames.csv"),
            errors: &errors,
            warnings: &warnings
        )
        let motion = try inspectMotion(
            directory.appendingPathComponent("imu.csv"),
            errors: &errors,
            warnings: &warnings
        )
        let face = try inspectFaces(
            directory.appendingPathComponent("face_anchors.csv"),
            errors: &errors,
            warnings: &warnings
        )
        let eventCount = try inspectEvents(
            directory.appendingPathComponent("events.csv"),
            errors: &errors
        )
        let captureStage = metadataCaptureStage(
            directory.appendingPathComponent("metadata.json")
        )
        let udpURL = directory.appendingPathComponent("udp_tx.csv")
        let hasUDPLog = FileManager.default.fileExists(atPath: udpURL.path)
        if captureStage == CaptureStage.phoneUDPProbeP2.rawValue, !hasUDPLog {
            errors.append("phone_udp_p2 会话缺少必需文件：udp_tx.csv")
        }
        let udp = hasUDPLog
            ? try inspectUDP(udpURL, errors: &errors, warnings: &warnings)
            : UDPInspection.empty

        let videoURL = directory.appendingPathComponent("rear_video.mov")
        let videoBytes = fileSize(videoURL)
        if ar.videoFrameCount == 0 {
            errors.append("没有成功写入任何视频帧。")
        }
        if ar.frameCount == 0 {
            errors.append("ar_frames.csv 没有数据行。")
        }
        if motion.sampleCount == 0 {
            errors.append("imu.csv 没有数据行。")
        }
        if face.sampleCount == 0 {
            warnings.append("本次会话没有观察到 ARFaceAnchor；请确认面部位于前置摄像头视野。")
        }
        if ar.missingRate > 0.01 {
            warnings.append(
                String(format: "视频—位姿映射缺失率为 %.3f%%，高于 1%%。", ar.missingRate * 100)
            )
        }

        let report = SessionValidationReport(
            schemaVersion: SessionValidationReport.schemaVersion,
            sessionID: sessionID,
            generatedAt: ISO8601Timestamp.string(from: Date()),
            passed: errors.isEmpty,
            errors: errors,
            warnings: warnings,
            statistics: .init(
                durationSeconds: ar.duration,
                videoBytes: videoBytes,
                arFrameCount: ar.frameCount,
                videoFrameCount: ar.videoFrameCount,
                videoDroppedFrameCount: ar.droppedFrameCount,
                videoMappingMissingRate: ar.missingRate,
                arTimestampGapMaximumSeconds: ar.maximumGap,
                trackingStateCounts: ar.trackingStates,
                imuSampleCount: motion.sampleCount,
                imuSamplesBySensor: motion.counts,
                imuEstimatedRatesHz: motion.rates,
                faceAnchorSampleCount: face.sampleCount,
                faceTrackedSampleCount: face.trackedCount,
                faceTrackedRatio: face.trackedRatio,
                eventCount: eventCount,
                udpPacketCount: udp.packetCount,
                udpSuccessfulPacketCount: udp.successfulPacketCount,
                udpFailedPacketCount: udp.failedPacketCount,
                udpSequenceGapCount: udp.sequenceGapCount,
                udpAchievedBitrateBitsPerSecond: udp.achievedBitrateBitsPerSecond
            )
        )
        return report
    }

    private static func inspectARFrames(
        _ url: URL,
        errors: inout [String],
        warnings: inout [String]
    ) throws -> ARInspection {
        guard FileManager.default.fileExists(atPath: url.path) else {
            return .empty
        }
        let rows = try CSVRows.read(url)
        guard rows.header.count == 34 else {
            errors.append("ar_frames.csv 表头列数不是预期的 34。")
            return .empty
        }

        var timestamps: [Double] = []
        var videoCount = 0
        var droppedCount = 0
        var trackingStates: [String: Int] = [:]

        for (index, row) in rows.data.enumerated() {
            guard row.count == rows.header.count else {
                errors.append("ar_frames.csv 第 \(index + 2) 行列数错误。")
                continue
            }
            guard let timestamp = Double(row[0]), timestamp.isFinite else {
                errors.append("ar_frames.csv 第 \(index + 2) 行时间戳无效。")
                continue
            }
            timestamps.append(timestamp)
            if UInt64(row[1]) == nil {
                errors.append("ar_frames.csv 第 \(index + 2) 行统一手机时钟无效。")
            }

            if row[5] == "true" {
                videoCount += 1
            } else {
                droppedCount += 1
            }

            let numericFields = row[6..<31]
            if numericFields.count != 25 || numericFields.contains(where: {
                guard let value = Double($0) else { return true }
                return !value.isFinite
            }) {
                errors.append("ar_frames.csv 第 \(index + 2) 行矩阵或内参包含无效数值。")
            }
            trackingStates[row[33], default: 0] += 1
        }

        checkStrictlyIncreasing(
            timestamps,
            label: "ARFrame",
            errors: &errors
        )
        let gaps = zip(timestamps.dropFirst(), timestamps).map { pair in
            pair.0 - pair.1
        }
        let maximumGap = gaps.max() ?? 0
        if maximumGap > 0.1 {
            warnings.append(
                String(format: "ARFrame 最大时间间隙为 %.6f 秒。", maximumGap)
            )
        }

        let normalCount = trackingStates["normal", default: 0]
        if !timestamps.isEmpty, Double(normalCount) / Double(timestamps.count) < 0.95 {
            warnings.append("ARKit normal 跟踪占比低于 95%。")
        }

        return ARInspection(
            frameCount: rows.data.count,
            videoFrameCount: videoCount,
            droppedFrameCount: droppedCount,
            duration: duration(timestamps),
            maximumGap: maximumGap,
            trackingStates: trackingStates
        )
    }

    private static func inspectMotion(
        _ url: URL,
        errors: inout [String],
        warnings: inout [String]
    ) throws -> MotionInspection {
        guard FileManager.default.fileExists(atPath: url.path) else {
            return .empty
        }
        let rows = try CSVRows.read(url)
        guard rows.header.count == 9 else {
            errors.append("imu.csv 表头列数不是预期的 9。")
            return .empty
        }

        var timestampsBySensor: [String: [Double]] = [:]
        for (index, row) in rows.data.enumerated() {
            guard row.count == rows.header.count else {
                errors.append("imu.csv 第 \(index + 2) 行列数错误。")
                continue
            }
            guard let timestamp = Double(row[0]), timestamp.isFinite else {
                errors.append("imu.csv 第 \(index + 2) 行时间戳无效。")
                continue
            }
            if UInt64(row[1]) == nil {
                errors.append("imu.csv 第 \(index + 2) 行统一手机时钟无效。")
            }
            let sensor = row[3]
            timestampsBySensor[sensor, default: []].append(timestamp)
            if row[4...6].contains(where: {
                guard let value = Double($0) else { return true }
                return !value.isFinite
            }) {
                errors.append("imu.csv 第 \(index + 2) 行包含无效数值。")
            }
        }

        var rates: [String: Double] = [:]
        var counts: [String: Int] = [:]
        for (sensor, timestamps) in timestampsBySensor {
            checkStrictlyIncreasing(
                timestamps,
                label: "IMU/\(sensor)",
                errors: &errors
            )
            counts[sensor] = timestamps.count
            let sensorDuration = duration(timestamps)
            if sensorDuration > 0 {
                rates[sensor] = Double(max(0, timestamps.count - 1)) / sensorDuration
            }
        }

        for sensor in ["accelerometer", "gyroscope", "device_motion_attitude_quaternion"] {
            guard let rate = rates[sensor] else {
                warnings.append("缺少 \(sensor) 数据流。")
                continue
            }
            if rate < 80 {
                warnings.append(
                    String(format: "%@ 估计采样率仅 %.2f Hz，低于 80 Hz。", sensor, rate)
                )
            }
        }

        return MotionInspection(
            sampleCount: rows.data.count,
            counts: counts,
            rates: rates
        )
    }

    private static func inspectFaces(
        _ url: URL,
        errors: inout [String],
        warnings: inout [String]
    ) throws -> FaceInspection {
        guard FileManager.default.fileExists(atPath: url.path) else {
            return .empty
        }
        let rows = try CSVRows.read(url)
        guard rows.header.count == 22 else {
            errors.append("face_anchors.csv 表头列数不是预期的 22。")
            return .empty
        }

        var timestamps: [Double] = []
        var trackedCount = 0
        for (index, row) in rows.data.enumerated() {
            guard row.count == rows.header.count else {
                errors.append("face_anchors.csv 第 \(index + 2) 行列数错误。")
                continue
            }
            if let timestamp = Double(row[0]), timestamp.isFinite {
                timestamps.append(timestamp)
            } else {
                errors.append("face_anchors.csv 第 \(index + 2) 行时间戳无效。")
            }
            if UInt64(row[1]) == nil {
                errors.append("face_anchors.csv 第 \(index + 2) 行统一手机时钟无效。")
            }
            if row[4] == "true" {
                trackedCount += 1
            }
            if row[6..<22].contains(where: {
                guard let value = Double($0) else { return true }
                return !value.isFinite
            }) {
                errors.append("face_anchors.csv 第 \(index + 2) 行变换矩阵无效。")
            }
        }

        if zip(timestamps.dropFirst(), timestamps).contains(where: { pair in
            pair.0 < pair.1
        }) {
            warnings.append("人脸锚点时间戳存在回退；ARAnchor 回调与 ARFrame 回调需进一步核对。")
        }

        return FaceInspection(
            sampleCount: rows.data.count,
            trackedCount: trackedCount
        )
    }

    private static func inspectEvents(
        _ url: URL,
        errors: inout [String]
    ) throws -> Int {
        guard FileManager.default.fileExists(atPath: url.path) else {
            return 0
        }
        let rows = try CSVRows.read(url)
        let eventTypes = Set(rows.data.compactMap { $0.count > 2 ? $0[2] : nil })
        if !eventTypes.contains("session_started") {
            errors.append("events.csv 缺少 session_started。")
        }
        if !eventTypes.contains("session_stopped") {
            errors.append("events.csv 缺少 session_stopped。")
        }
        return rows.data.count
    }

    private static func inspectUDP(
        _ url: URL,
        errors: inout [String],
        warnings: inout [String]
    ) throws -> UDPInspection {
        let rows = try CSVRows.read(url)
        guard rows.header.count == 9 else {
            errors.append("udp_tx.csv 表头列数不是预期的 9。")
            return .empty
        }

        var previousSequence: UInt64?
        var firstPhoneNanoseconds: UInt64?
        var lastPhoneNanoseconds: UInt64?
        var successfulPackets = 0
        var failedPackets = 0
        var successfulBytes = 0
        var sequenceGaps = 0

        for (index, row) in rows.data.enumerated() {
            guard row.count == rows.header.count else {
                errors.append("udp_tx.csv 第 \(index + 2) 行列数错误。")
                continue
            }
            guard let sequence = UInt64(row[0]),
                  let phoneNanoseconds = UInt64(row[1]),
                  let datagramBytes = Int(row[4]), datagramBytes > 0 else {
                errors.append("udp_tx.csv 第 \(index + 2) 行字段无效。")
                continue
            }

            if let previousSequence {
                if sequence <= previousSequence {
                    errors.append("udp_tx.csv sequence 不是严格递增。")
                } else if sequence > previousSequence + 1 {
                    sequenceGaps += Int(sequence - previousSequence - 1)
                }
            }
            previousSequence = sequence
            firstPhoneNanoseconds = firstPhoneNanoseconds ?? phoneNanoseconds
            lastPhoneNanoseconds = phoneNanoseconds

            if row[7] == "accepted_by_local_udp_stack" {
                successfulPackets += 1
                successfulBytes += datagramBytes
            } else {
                failedPackets += 1
            }
        }

        if rows.data.isEmpty {
            errors.append("udp_tx.csv 没有数据行。")
        }
        if sequenceGaps > 0 {
            warnings.append("udp_tx.csv 存在 \(sequenceGaps) 个发送序号缺口。")
        }
        if failedPackets > 2 {
            warnings.append("udp_tx.csv 有 \(failedPackets) 个本地发送失败包。")
        }
        let durationSeconds: Double
        if let firstPhoneNanoseconds, let lastPhoneNanoseconds,
           lastPhoneNanoseconds > firstPhoneNanoseconds {
            durationSeconds = Double(lastPhoneNanoseconds - firstPhoneNanoseconds)
                / 1_000_000_000
        } else {
            durationSeconds = 0
        }
        let bitrate = durationSeconds > 0
            ? Double(successfulBytes * 8) / durationSeconds
            : 0

        return UDPInspection(
            packetCount: rows.data.count,
            successfulPacketCount: successfulPackets,
            failedPacketCount: failedPackets,
            sequenceGapCount: sequenceGaps,
            achievedBitrateBitsPerSecond: bitrate
        )
    }

    private static func metadataCaptureStage(_ url: URL) -> String? {
        guard let data = try? Data(contentsOf: url),
              let object = try? JSONSerialization.jsonObject(with: data),
              let dictionary = object as? [String: Any] else {
            return nil
        }
        return dictionary["capture_stage"] as? String
    }

    private static func checkStrictlyIncreasing(
        _ timestamps: [Double],
        label: String,
        errors: inout [String]
    ) {
        if zip(timestamps.dropFirst(), timestamps).contains(where: { pair in
            pair.0 <= pair.1
        }) {
            errors.append("\(label) 时间戳不是严格单调递增。")
        }
    }

    private static func duration(_ timestamps: [Double]) -> Double {
        guard let first = timestamps.first, let last = timestamps.last else { return 0 }
        return max(0, last - first)
    }

    private static func fileSize(_ url: URL) -> Int64 {
        let value = try? url.resourceValues(forKeys: [.fileSizeKey]).fileSize
        return Int64(value ?? 0)
    }
}

private struct CSVRows {
    let header: [String]
    let data: [[String]]

    static func read(_ url: URL) throws -> CSVRows {
        let text = try String(contentsOf: url, encoding: .utf8)
        let lines = text.split(whereSeparator: \.isNewline)
        guard let first = lines.first else {
            return CSVRows(header: [], data: [])
        }
        return CSVRows(
            header: parseLine(String(first)),
            data: lines.dropFirst().map { parseLine(String($0)) }
        )
    }

    private static func parseLine(_ line: String) -> [String] {
        var fields: [String] = []
        var current = ""
        var insideQuotes = false
        var index = line.startIndex

        while index < line.endIndex {
            let character = line[index]
            if character == "\"" {
                let next = line.index(after: index)
                if insideQuotes, next < line.endIndex, line[next] == "\"" {
                    current.append("\"")
                    index = line.index(after: next)
                    continue
                }
                insideQuotes.toggle()
            } else if character == ",", !insideQuotes {
                fields.append(current)
                current = ""
            } else {
                current.append(character)
            }
            index = line.index(after: index)
        }
        fields.append(current)
        return fields
    }
}

private struct ARInspection {
    let frameCount: Int
    let videoFrameCount: Int
    let droppedFrameCount: Int
    let duration: Double
    let maximumGap: Double
    let trackingStates: [String: Int]

    var missingRate: Double {
        guard frameCount > 0 else { return 1 }
        return Double(droppedFrameCount) / Double(frameCount)
    }

    static let empty = ARInspection(
        frameCount: 0,
        videoFrameCount: 0,
        droppedFrameCount: 0,
        duration: 0,
        maximumGap: 0,
        trackingStates: [:]
    )
}

private struct MotionInspection {
    let sampleCount: Int
    let counts: [String: Int]
    let rates: [String: Double]

    static let empty = MotionInspection(sampleCount: 0, counts: [:], rates: [:])
}

private struct FaceInspection {
    let sampleCount: Int
    let trackedCount: Int

    var trackedRatio: Double {
        guard sampleCount > 0 else { return 0 }
        return Double(trackedCount) / Double(sampleCount)
    }

    static let empty = FaceInspection(sampleCount: 0, trackedCount: 0)
}

private struct UDPInspection {
    let packetCount: Int
    let successfulPacketCount: Int
    let failedPacketCount: Int
    let sequenceGapCount: Int
    let achievedBitrateBitsPerSecond: Double

    static let empty = UDPInspection(
        packetCount: 0,
        successfulPacketCount: 0,
        failedPacketCount: 0,
        sequenceGapCount: 0,
        achievedBitrateBitsPerSecond: 0
    )
}

enum ISO8601Timestamp {
    private static let formatter: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter
    }()

    static func string(from date: Date) -> String {
        formatter.string(from: date)
    }
}
