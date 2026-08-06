import XCTest
@testable import WiTwinRecorder

final class CapabilityReportTests: XCTestCase {
    func testCapabilityReportEncodingUsesStableSchemaAndKeys() throws {
        let report = CapabilityReport(
            schemaVersion: CapabilityReport.schemaVersion,
            generatedAt: "2026-07-28T00:00:00.000Z",
            monotonicTimestampSeconds: 123,
            executionEnvironment: .init(isSimulator: true, requiresPhysicalDeviceValidation: true),
            device: .init(
                modelName: "iPhone Simulator",
                modelIdentifier: "arm64",
                systemName: "iOS",
                systemVersion: "26.5"
            ),
            app: .init(version: "0.1.0", build: "1"),
            arkit: .init(
                worldTrackingSupported: false,
                worldTrackingSupportsUserFaceTracking: false,
                faceTrackingSupported: false
            ),
            camera: .init(
                authorizationStatus: "not_determined",
                availableDevices: [],
                capturedImageWidth: nil,
                capturedImageHeight: nil,
                imageResolutionWidth: nil,
                imageResolutionHeight: nil,
                intrinsics3x3RowMajor: nil
            ),
            motion: .init(
                authorizationStatus: "not_determined",
                accelerometerAvailable: false,
                gyroAvailable: false,
                deviceMotionAvailable: false,
                magnetometerAvailable: false
            ),
            storage: .init(
                documentsDirectory: "/tmp",
                volumeAvailableCapacityBytes: 1,
                volumeAvailableCapacityForImportantUsageBytes: 1
            ),
            thermalState: "nominal",
            runtimeValidation: .init(
                status: "world_tracking_unsupported",
                arFrameReceived: false,
                arFrameTimestampSeconds: nil,
                trackingState: nil,
                worldTransform4x4RowMajor: nil,
                userFaceTrackingEnabled: false,
                faceAnchorObserved: false,
                faceAnchorFrameTimestampSeconds: nil,
                faceAnchorTransform4x4RowMajor: nil,
                notes: ["simulator"]
            )
        )

        let data = try CapabilityReportWriter.encode(report)
        let object = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])

        XCTAssertEqual(object["schema_version"] as? String, "1.0.0")
        XCTAssertNotNil(object["arkit"])
        XCTAssertNotNil(object["runtime_validation"])
        XCTAssertTrue(String(decoding: data, as: UTF8.self).contains("\n"))
    }

    func testCapabilityReportRoundTripsWithoutLosingFields() throws {
        let json = """
        {
          "app": {"build":"1","version":"0.1.0"},
          "arkit": {
            "faceTrackingSupported":true,
            "worldTrackingSupported":true,
            "worldTrackingSupportsUserFaceTracking":true
          },
          "camera": {
            "authorizationStatus":"authorized",
            "availableDevices":[],
            "capturedImageHeight":1080,
            "capturedImageWidth":1920,
            "imageResolutionHeight":1080,
            "imageResolutionWidth":1920,
            "intrinsics3x3RowMajor":[1,0,0,0,1,0,0,0,1]
          },
          "device": {
            "modelIdentifier":"iPhone12,3",
            "modelName":"iPhone",
            "systemName":"iOS",
            "systemVersion":"18.0"
          },
          "execution_environment": {
            "is_simulator":false,
            "requires_physical_device_validation":false
          },
          "generated_at":"2026-07-28T00:00:00.000Z",
          "monotonic_timestamp_seconds":123,
          "motion": {
            "accelerometerAvailable":true,
            "authorizationStatus":"authorized",
            "deviceMotionAvailable":true,
            "gyroAvailable":true,
            "magnetometerAvailable":true
          },
          "runtime_validation": {
            "ar_frame_received":true,
            "ar_frame_timestamp_seconds":120,
            "face_anchor_observed":true,
            "face_anchor_frame_timestamp_seconds":120,
            "face_anchor_transform4x4_row_major":[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1],
            "notes":[],
            "status":"ar_frame_received",
            "tracking_state":"normal",
            "user_face_tracking_enabled":true,
            "world_transform4x4_row_major":[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]
          },
          "schema_version":"1.0.0",
          "storage": {
            "documents_directory":"/documents",
            "volume_available_capacity_bytes":100,
            "volume_available_capacity_for_important_usage_bytes":100
          },
          "thermal_state":"nominal"
        }
        """

        let decoded = try CapabilityReportWriter.decode(Data(json.utf8))

        XCTAssertEqual(decoded.device.modelIdentifier, "iPhone12,3")
        XCTAssertEqual(decoded.camera.intrinsics3x3RowMajor?.count, 9)
        XCTAssertEqual(decoded.runtimeValidation.worldTransform4x4RowMajor?.count, 16)
        XCTAssertEqual(decoded.runtimeValidation.faceAnchorTransform4x4RowMajor?.count, 16)
        XCTAssertTrue(decoded.runtimeValidation.faceAnchorObserved)
    }

    func testSessionMetadataUsesPhoneOnlyP1Schema() throws {
        let metadata = SessionMetadata(
            schemaVersion: SessionMetadata.schemaVersion,
            sessionID: "session_20260729_120000",
            captureStage: .phoneOnlyP1,
            createdAt: "2026-07-29T04:00:00.000Z",
            completedAt: "2026-07-29T04:01:00.000Z",
            status: "completed",
            source: .init(
                workspaceCommit: "unknown",
                buildIdentifier: "org.witwin.recorder/0.4.0(1)"
            ),
            devices: .init(
                phone: .init(
                    model: "iPhone",
                    modelIdentifier: "iPhone12,3",
                    osVersion: "26.3.1",
                    appVersion: "0.2.0",
                    appBuild: "1"
                )
            ),
            assembly: .init(phoneAssemblyID: "phone-rig-001"),
            timebases: .init(phone: .init(clock: "mach_continuous_time_seconds", unit: "s")),
            coordinateConvention: "schemas/session-format/coordinate_frames.md",
            capture: .init(
                startedMonotonicSeconds: 100,
                endedMonotonicSeconds: 160,
                durationSeconds: 60,
                videoFrameCount: 3600,
                videoDroppedFrameCount: 0,
                arFrameCount: 3600,
                faceAnchorSampleCount: 100,
                imuSampleCount: 30_000,
                thermalStateAtStart: "nominal",
                maximumThermalState: "fair",
                thermalStateAtEnd: "fair",
                availableCapacityBytesAtStart: 1_000_000,
                availableCapacityBytesAtEnd: 900_000,
                video: .init(
                    codec: "hevc",
                    container: "quicktime_mov",
                    sourcePixelFormatFourCC: "420f",
                    expectedFrameRateHz: 60,
                    width: 1920,
                    height: 1440,
                    orientation: "arkit_captured_image_sensor_native",
                    mirrored: false,
                    cropPolicy: "none",
                    scalingPolicy: "none",
                    stabilizationPolicy: "no_additional_recorder_stabilization",
                    videoFrameIDSemantics: "zero_based_successful_asset_writer_sample_index"
                ),
                arkit: .init(
                    poseFieldPrefix: "world_T_rear_camera",
                    transformConvention: "target_T_source",
                    matrixLayout: "row_major",
                    coordinateSystem: "right_handed_arkit_world",
                    lengthUnit: "m",
                    intrinsicsMatrixLayout: "row_major",
                    intrinsicsReference: "frame.camera.imageResolution"
                ),
                motion: .init(
                    requestedUpdateRateHz: 100,
                    attitudeReferenceFrame: "xArbitraryZVertical",
                    quaternionOrder: "xyzw",
                    rawSamplesInterpolated: false,
                    recordedStreams: ["accelerometer"],
                    streams: [
                        "accelerometer": .init(unit: "g", referenceFrame: "device_body")
                    ]
                ),
                udp: nil
            ),
            files: []
        )

        let data = try SessionJSON.encode(metadata)
        let object = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        XCTAssertEqual(object["schema_version"] as? String, "1.3.0")
        XCTAssertEqual(object["capture_stage"] as? String, "phone_only_p1")
        let devices = try XCTUnwrap(object["devices"] as? [String: Any])
        XCTAssertNotNil(devices["phone"])
        XCTAssertNil(devices["csi_receiver"])
        let capture = try XCTUnwrap(object["capture"] as? [String: Any])
        let video = try XCTUnwrap(capture["video"] as? [String: Any])
        XCTAssertEqual(video["video_frame_id_semantics"] as? String,
                       "zero_based_successful_asset_writer_sample_index")
        let motion = try XCTUnwrap(capture["motion"] as? [String: Any])
        XCTAssertEqual(motion["raw_samples_interpolated"] as? Bool, false)
    }

    func testVideoSampleIndexerOnlyAdvancesForAppendedSamples() {
        var indexer = VideoSampleIndexer()

        XCTAssertEqual(indexer.recordAppend(success: true), 0)
        XCTAssertNil(indexer.recordAppend(success: false))
        XCTAssertNil(indexer.recordAppend(success: false))
        XCTAssertEqual(indexer.recordAppend(success: true), 1)
        XCTAssertEqual(indexer.nextSampleID, 2)
    }

    func testSessionIntegrityValidatorAcceptsMinimalCompleteSession() throws {
        let directory = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: directory) }

        for name in ["metadata.json", "capabilities.json", "assembly.json"] {
            try Data("{}".utf8).write(to: directory.appendingPathComponent(name))
        }
        try Data([0, 1, 2, 3]).write(to: directory.appendingPathComponent("rear_video.mov"))

        let arHeader = [
            "timestamp_seconds", "callback_phone_monotonic_ns", "frame_id",
            "video_frame_id", "video_pts_seconds", "video_appended"
        ] + (0..<16).map { "m\($0)" } + (0..<9).map { "k\($0)" } + [
            "image_width", "image_height", "tracking_state"
        ]
        let arRow = [
            "100.0", "100000000000", "0", "0", "0.0", "true"
        ] + (0..<16).map { $0 % 5 == 0 ? "1" : "0" } + [
            "1000", "0", "500", "0", "1000", "500", "0", "0", "1",
            "1920", "1440", "normal"
        ]
        try writeCSV(
            header: arHeader,
            rows: [arRow],
            to: directory.appendingPathComponent("ar_frames.csv")
        )

        let faceHeader = [
            "timestamp_seconds", "callback_phone_monotonic_ns", "frame_id",
            "anchor_id", "is_tracked", "event"
        ] + (0..<16).map { "f\($0)" }
        try writeCSV(
            header: faceHeader,
            rows: [],
            to: directory.appendingPathComponent("face_anchors.csv")
        )

        let imuHeader = [
            "timestamp_seconds", "callback_phone_monotonic_ns", "sample_id",
            "sensor_type", "x", "y", "z", "w", "accuracy"
        ]
        let imuRows = [
            ["100.0", "100000000001", "0", "accelerometer", "0", "0", "1", "", ""],
            ["100.0", "100000000002", "1", "gyroscope", "0", "0", "0", "", ""],
            ["100.0", "100000000003", "2", "device_motion_attitude_quaternion", "0", "0", "0", "1", ""]
        ]
        try writeCSV(
            header: imuHeader,
            rows: imuRows,
            to: directory.appendingPathComponent("imu.csv")
        )
        try writeCSV(
            header: ["timestamp_seconds", "wall_time", "event_type", "detail"],
            rows: [
                ["100.0", "2026-07-29T04:00:00Z", "session_started", "phone_only_p1"],
                ["101.0", "2026-07-29T04:00:01Z", "session_stopped", "user"]
            ],
            to: directory.appendingPathComponent("events.csv")
        )

        let report = try SessionIntegrityValidator.validate(
            sessionID: "session_test",
            directory: directory
        )
        XCTAssertTrue(report.passed, report.errors.joined(separator: "\n"))
        XCTAssertEqual(report.statistics.arFrameCount, 1)
        XCTAssertEqual(report.statistics.videoFrameCount, 1)
        XCTAssertEqual(report.statistics.imuSampleCount, 3)

        try Data(#"{"capture_stage":"phone_udp_p2"}"#.utf8).write(
            to: directory.appendingPathComponent("metadata.json")
        )
        let missingUDPReport = try SessionIntegrityValidator.validate(
            sessionID: "session_test_missing_udp",
            directory: directory
        )
        XCTAssertFalse(missingUDPReport.passed)
        XCTAssertTrue(
            missingUDPReport.errors.contains {
                $0.contains("phone_udp_p2") && $0.contains("udp_tx.csv")
            }
        )
    }

    @MainActor
    func testP1RecorderFiveSecondPhysicalDeviceSmoke() async throws {
        #if targetEnvironment(simulator)
        throw XCTSkip("P1 采集冒烟测试必须在支持 ARKit 的真机运行。")
        #else
        let documents = try FileManager.default.url(
            for: .documentDirectory,
            in: .userDomainMask,
            appropriateFor: nil,
            create: true
        )
        guard FileManager.default.fileExists(
            atPath: documents.appendingPathComponent("capabilities.json").path
        ) else {
            throw XCTSkip("真机 App 容器内没有 P0 capabilities.json。")
        }

        let recorder = SessionRecorder()
        recorder.start(phoneAssemblyID: "automated-test-rig")
        try await waitForRecorder(recorder, toEnter: .recording, timeout: 15)
        try await Task.sleep(nanoseconds: 5_000_000_000)
        recorder.stop(reason: "xctest_five_second_smoke")
        try await waitForRecorderToFinish(recorder, timeout: 30)

        XCTAssertEqual(recorder.state, .completed, recorder.statusMessage)
        let report = try XCTUnwrap(recorder.validationReport)
        XCTAssertTrue(report.passed, report.errors.joined(separator: "\n"))
        XCTAssertGreaterThan(report.statistics.videoFrameCount, 0)
        XCTAssertGreaterThan(report.statistics.arFrameCount, 0)
        XCTAssertGreaterThan(report.statistics.imuSampleCount, 0)
        XCTAssertEqual(report.statistics.videoMappingMissingRate, 0, accuracy: 0.01)
        #endif
    }

    func testUDPProbePacketUsesStableNetworkByteOrder() throws {
        let packet = try UDPProbePacket.encode(
            sessionID: "udp_test",
            sequence: 0x0102030405060708,
            phoneMonotonicNanoseconds: 0x1112131415161718,
            datagramBytes: 1_200
        )

        XCTAssertEqual(packet.count, 1_200)
        XCTAssertEqual(Data(packet[0..<4]), Data("WTWN".utf8))
        XCTAssertEqual(packet[4], 1)
        XCTAssertEqual(packet[5], 0)
        XCTAssertEqual(Array(packet[6..<8]), [0, 32])
        XCTAssertEqual(
            Array(packet[16..<24]),
            [1, 2, 3, 4, 5, 6, 7, 8]
        )
        XCTAssertEqual(
            Array(packet[24..<32]),
            [17, 18, 19, 20, 21, 22, 23, 24]
        )
        XCTAssertEqual(UDPProbePacket.sessionHashHex("udp_test").count, 16)
    }

    func testUDPProbeAcknowledgementHeaderRoundTrips() throws {
        let sessionID = "session_20260730_120000.preflight"
        let packet = try UDPProbePacket.encode(
            sessionID: sessionID,
            sequence: 4,
            phoneMonotonicNanoseconds: 123_456_789,
            datagramBytes: UDPProbePacket.headerLength,
            flags: .acknowledgement
        )

        let header = try XCTUnwrap(UDPProbePacket.decodeHeader(packet))
        XCTAssertEqual(header.flags, .acknowledgement)
        XCTAssertEqual(header.sessionHash, UDPProbePacket.sessionHash(sessionID))
        XCTAssertEqual(header.sequence, 4)
        XCTAssertEqual(header.phoneMonotonicNanoseconds, 123_456_789)
    }

    func testLiveUDPProbeToPicoScenesHost() async throws {
        #if targetEnvironment(simulator)
        throw XCTSkip("实时 UDP 上行测试必须在 iPhone 真机运行。")
        #else
        guard ProcessInfo.processInfo.environment["WITWIN_RUN_LIVE_UDP"] == "1" else {
            throw XCTSkip("设置 WITWIN_RUN_LIVE_UDP=1 后才运行实时局域网发包测试。")
        }
        let durationText =
            ProcessInfo.processInfo.environment["WITWIN_UDP_DURATION_SECONDS"] ?? "10"
        guard let durationSeconds = UInt64(durationText),
              (1...600).contains(durationSeconds) else {
            XCTFail("WITWIN_UDP_DURATION_SECONDS 必须是 1 到 600 之间的整数。")
            return
        }
        let documents = try FileManager.default.url(
            for: .documentDirectory,
            in: .userDomainMask,
            appropriateFor: nil,
            create: true
        )
        let root = documents.appendingPathComponent("UDPTests", isDirectory: true)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        let sessionID = "udp_test_\(Int(Date().timeIntervalSince1970))"
        let directory = root.appendingPathComponent(sessionID, isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: false)

        let ready = expectation(description: "UDP Wi-Fi path ready")
        let sender = try UDPProbeSender(
            configuration: UDPProbeConfiguration(
                host: ProcessInfo.processInfo.environment["WITWIN_UDP_HOST"]
                    ?? UDPProbeConfiguration.defaultHost,
                port: UDPProbeConfiguration.defaultPort,
                bitrateBitsPerSecond: UDPProbeConfiguration.defaultBitrateBitsPerSecond,
                datagramBytes: UDPProbeConfiguration.defaultDatagramBytes
            ),
            sessionID: sessionID,
            logURL: directory.appendingPathComponent("udp_tx.csv"),
            stateHandler: { state in
                if state == .sending {
                    ready.fulfill()
                }
            }
        )
        try sender.start()
        await fulfillment(of: [ready], timeout: 10)
        try await Task.sleep(nanoseconds: durationSeconds * 1_000_000_000)

        let stopped = expectation(description: "UDP sender stopped")
        var result: Result<UDPProbeStatistics, Error>?
        sender.stop {
            result = $0
            stopped.fulfill()
        }
        await fulfillment(of: [stopped], timeout: 5)

        let statistics = try XCTUnwrap(result).get()
        XCTAssertGreaterThan(statistics.successfulPackets, Int(durationSeconds) * 180)
        XCTAssertEqual(statistics.failedPackets, 0)
        XCTAssertEqual(
            statistics.achievedBitrateBitsPerSecond,
            2_000_000,
            accuracy: 100_000
        )
        #endif
    }

    @MainActor
    func testLiveP2RecorderPhysicalDevice() async throws {
        #if targetEnvironment(simulator)
        throw XCTSkip("P2 联合采集测试必须在支持 ARKit 的真机运行。")
        #else
        guard ProcessInfo.processInfo.environment["WITWIN_RUN_LIVE_UDP"] == "1" else {
            throw XCTSkip("设置 WITWIN_RUN_LIVE_UDP=1 后才运行实时 P2 联合采集测试。")
        }
        let durationText =
            ProcessInfo.processInfo.environment["WITWIN_RECORDER_DURATION_SECONDS"] ?? "5"
        guard let durationSeconds = UInt64(durationText),
              (1...120).contains(durationSeconds) else {
            XCTFail("WITWIN_RECORDER_DURATION_SECONDS 必须是 1 到 120 之间的整数。")
            return
        }
        let documents = try FileManager.default.url(
            for: .documentDirectory,
            in: .userDomainMask,
            appropriateFor: nil,
            create: true
        )
        guard FileManager.default.fileExists(
            atPath: documents.appendingPathComponent("capabilities.json").path
        ) else {
            throw XCTSkip("真机 App 容器内没有 P0 capabilities.json。")
        }

        let recorder = SessionRecorder()
        recorder.start(
            phoneAssemblyID: "automated-p2-test-rig",
            udpConfiguration: UDPProbeConfiguration(
                host: ProcessInfo.processInfo.environment["WITWIN_UDP_HOST"]
                    ?? UDPProbeConfiguration.defaultHost,
                port: UDPProbeConfiguration.defaultPort,
                bitrateBitsPerSecond: UDPProbeConfiguration.defaultBitrateBitsPerSecond,
                datagramBytes: UDPProbeConfiguration.defaultDatagramBytes
            )
        )
        try await waitForRecorder(recorder, toEnter: .recording, timeout: 15)
        try await Task.sleep(nanoseconds: durationSeconds * 1_000_000_000)
        recorder.stop(reason: "xctest_p2_\(durationSeconds)_second_smoke")
        try await waitForRecorderToFinish(recorder, timeout: 30)

        XCTAssertEqual(recorder.state, .completed, recorder.statusMessage)
        let report = try XCTUnwrap(recorder.validationReport)
        XCTAssertTrue(report.passed, report.errors.joined(separator: "\n"))
        XCTAssertGreaterThan(report.statistics.videoFrameCount, 0)
        XCTAssertGreaterThan(report.statistics.arFrameCount, 0)
        XCTAssertGreaterThan(report.statistics.imuSampleCount, 0)
        XCTAssertGreaterThan(
            report.statistics.udpSuccessfulPacketCount,
            Int(durationSeconds) * 100
        )
        XCTAssertEqual(report.statistics.udpFailedPacketCount, 0)
        XCTAssertEqual(report.statistics.udpSequenceGapCount, 0)

        let sessionURL = try XCTUnwrap(recorder.lastSessionURL)
        let metadata = try JSONSerialization.jsonObject(
            with: Data(contentsOf: sessionURL.appendingPathComponent("metadata.json"))
        ) as? [String: Any]
        XCTAssertEqual(metadata?["capture_stage"] as? String, "phone_udp_p2")
        #endif
    }

    private func writeCSV(header: [String], rows: [[String]], to url: URL) throws {
        let lines = ([header] + rows).map { $0.joined(separator: ",") }
        try Data((lines.joined(separator: "\n") + "\n").utf8).write(to: url)
    }

    @MainActor
    private func waitForRecorder(
        _ recorder: SessionRecorder,
        toEnter expectedState: RecordingState,
        timeout: TimeInterval
    ) async throws {
        let deadline = Date().addingTimeInterval(timeout)
        while recorder.state != expectedState, Date() < deadline {
            if recorder.state == .failed {
                XCTFail(recorder.statusMessage)
                return
            }
            try await Task.sleep(nanoseconds: 100_000_000)
        }
        XCTAssertEqual(recorder.state, expectedState, recorder.statusMessage)
    }

    @MainActor
    private func waitForRecorderToFinish(
        _ recorder: SessionRecorder,
        timeout: TimeInterval
    ) async throws {
        let deadline = Date().addingTimeInterval(timeout)
        while recorder.state == .recording
                || recorder.state == .stopping
                || recorder.state == .preparing,
              Date() < deadline {
            try await Task.sleep(nanoseconds: 100_000_000)
        }
        XCTAssertTrue(
            recorder.state == .completed || recorder.state == .failed,
            recorder.statusMessage
        )
    }
}
