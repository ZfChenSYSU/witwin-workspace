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
}
