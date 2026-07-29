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
                availableCapacityBytesAtEnd: 900_000
            ),
            files: []
        )

        let data = try SessionJSON.encode(metadata)
        let object = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        XCTAssertEqual(object["schema_version"] as? String, "1.1.0")
        XCTAssertEqual(object["capture_stage"] as? String, "phone_only_p1")
        let devices = try XCTUnwrap(object["devices"] as? [String: Any])
        XCTAssertNotNil(devices["phone"])
        XCTAssertNil(devices["csi_receiver"])
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
            "timestamp_seconds", "frame_id", "video_frame_id", "video_pts_seconds",
            "video_appended"
        ] + (0..<16).map { "m\($0)" } + (0..<9).map { "k\($0)" } + [
            "image_width", "image_height", "tracking_state"
        ]
        let arRow = [
            "100.0", "0", "0", "0.0", "true"
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
            "timestamp_seconds", "frame_id", "anchor_id", "is_tracked", "event"
        ] + (0..<16).map { "f\($0)" }
        try writeCSV(
            header: faceHeader,
            rows: [],
            to: directory.appendingPathComponent("face_anchors.csv")
        )

        let imuHeader = [
            "timestamp_seconds", "sample_id", "sensor_type", "x", "y", "z", "w", "accuracy"
        ]
        let imuRows = [
            ["100.0", "0", "accelerometer", "0", "0", "1", "", ""],
            ["100.0", "1", "gyroscope", "0", "0", "0", "", ""],
            ["100.0", "2", "device_motion_attitude_quaternion", "0", "0", "0", "1", ""]
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
