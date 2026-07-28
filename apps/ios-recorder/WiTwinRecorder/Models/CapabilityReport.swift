import Foundation

struct CapabilityReport: Codable, Equatable {
    static let schemaVersion = "1.0.0"

    let schemaVersion: String
    let generatedAt: String
    let monotonicTimestampSeconds: TimeInterval
    let executionEnvironment: ExecutionEnvironment
    let device: DeviceCapabilities
    let app: AppCapabilities
    let arkit: ARKitCapabilities
    let camera: CameraCapabilities
    let motion: MotionCapabilities
    let storage: StorageCapabilities
    let thermalState: String
    let runtimeValidation: RuntimeValidation

    struct ExecutionEnvironment: Codable, Equatable {
        let isSimulator: Bool
        let requiresPhysicalDeviceValidation: Bool
    }

    struct DeviceCapabilities: Codable, Equatable {
        let modelName: String
        let modelIdentifier: String
        let systemName: String
        let systemVersion: String
    }

    struct AppCapabilities: Codable, Equatable {
        let version: String
        let build: String
    }

    struct ARKitCapabilities: Codable, Equatable {
        let worldTrackingSupported: Bool
        let worldTrackingSupportsUserFaceTracking: Bool
        let faceTrackingSupported: Bool
    }

    struct CameraDevice: Codable, Equatable {
        let uniqueID: String
        let localizedName: String
        let position: String
        let deviceType: String
    }

    struct CameraCapabilities: Codable, Equatable {
        let authorizationStatus: String
        let availableDevices: [CameraDevice]
        let capturedImageWidth: Int?
        let capturedImageHeight: Int?
        let imageResolutionWidth: Int?
        let imageResolutionHeight: Int?
        let intrinsics3x3RowMajor: [Float]?
    }

    struct MotionCapabilities: Codable, Equatable {
        let authorizationStatus: String
        let accelerometerAvailable: Bool
        let gyroAvailable: Bool
        let deviceMotionAvailable: Bool
        let magnetometerAvailable: Bool
    }

    struct StorageCapabilities: Codable, Equatable {
        let documentsDirectory: String
        let volumeAvailableCapacityBytes: Int64?
        let volumeAvailableCapacityForImportantUsageBytes: Int64?
    }

    struct RuntimeValidation: Codable, Equatable {
        let status: String
        let arFrameReceived: Bool
        let arFrameTimestampSeconds: TimeInterval?
        let trackingState: String?
        let worldTransform4x4RowMajor: [Float]?
        let userFaceTrackingEnabled: Bool
        let faceAnchorObserved: Bool
        let faceAnchorFrameTimestampSeconds: TimeInterval?
        let faceAnchorTransform4x4RowMajor: [Float]?
        let notes: [String]
    }
}

enum CapabilityReportWriter {
    static func encode(_ report: CapabilityReport) throws -> Data {
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
        return try encoder.encode(report)
    }

    static func decode(_ data: Data) throws -> CapabilityReport {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .custom { codingPath in
            let key = codingPath[codingPath.count - 1]
            let components = key.stringValue.split(separator: "_")

            guard components.count > 1 else {
                return key
            }

            let camelCaseKey = String(components[0]) + components.dropFirst().map { component in
                component.prefix(1).uppercased() + component.dropFirst()
            }.joined()

            return ReportCodingKey(stringValue: camelCaseKey) ?? key
        }
        return try decoder.decode(CapabilityReport.self, from: data)
    }

    static func write(_ report: CapabilityReport, to directory: URL) throws -> URL {
        let destination = directory.appendingPathComponent("capabilities.json")
        try encode(report).write(to: destination, options: .atomic)
        return destination
    }
}

private struct ReportCodingKey: CodingKey {
    let stringValue: String
    let intValue: Int?

    init?(stringValue: String) {
        self.stringValue = stringValue
        intValue = nil
    }

    init?(intValue: Int) {
        stringValue = String(intValue)
        self.intValue = intValue
    }
}
