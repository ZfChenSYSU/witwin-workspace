import Foundation

enum CaptureStage: String, Codable {
    case phoneOnlyP1 = "phone_only_p1"
    case phoneUDPProbeP2 = "phone_udp_p2"
}

enum RecordingState: String, Codable {
    case idle
    case preparing
    case recording
    case stopping
    case completed
    case failed
}

struct SessionMetadata: Codable, Equatable {
    static let schemaVersion = "1.3.0"

    let schemaVersion: String
    let sessionID: String
    let captureStage: CaptureStage
    let createdAt: String
    let completedAt: String
    let status: String
    let source: Source
    let devices: Devices
    let assembly: Assembly
    let timebases: Timebases
    let coordinateConvention: String
    let capture: CaptureSummary
    let files: [SessionFile]

    struct Source: Codable, Equatable {
        let workspaceCommit: String
        let buildIdentifier: String
    }

    struct Devices: Codable, Equatable {
        let phone: Phone
    }

    struct Phone: Codable, Equatable {
        let model: String
        let modelIdentifier: String
        let osVersion: String
        let appVersion: String
        let appBuild: String
    }

    struct Assembly: Codable, Equatable {
        let phoneAssemblyID: String
    }

    struct Timebases: Codable, Equatable {
        let phone: Timebase
    }

    struct Timebase: Codable, Equatable {
        let clock: String
        let unit: String
    }

    struct CaptureSummary: Codable, Equatable {
        let startedMonotonicSeconds: TimeInterval
        let endedMonotonicSeconds: TimeInterval
        let durationSeconds: TimeInterval
        let videoFrameCount: Int
        let videoDroppedFrameCount: Int
        let arFrameCount: Int
        let faceAnchorSampleCount: Int
        let imuSampleCount: Int
        let thermalStateAtStart: String
        let maximumThermalState: String
        let thermalStateAtEnd: String
        let availableCapacityBytesAtStart: Int64?
        let availableCapacityBytesAtEnd: Int64?
        let video: VideoSemantics
        let arkit: ARKitSemantics
        let motion: MotionSemantics
        let udp: UDPSummary?
    }

    struct VideoSemantics: Codable, Equatable {
        let codec: String
        let container: String
        let sourcePixelFormatFourCC: String?
        let expectedFrameRateHz: Double
        let width: Int?
        let height: Int?
        let orientation: String
        let mirrored: Bool
        let cropPolicy: String
        let scalingPolicy: String
        let stabilizationPolicy: String
        let videoFrameIDSemantics: String
    }

    struct ARKitSemantics: Codable, Equatable {
        let poseFieldPrefix: String
        let transformConvention: String
        let matrixLayout: String
        let coordinateSystem: String
        let lengthUnit: String
        let intrinsicsMatrixLayout: String
        let intrinsicsReference: String
    }

    struct MotionSemantics: Codable, Equatable {
        let requestedUpdateRateHz: Double
        let attitudeReferenceFrame: String
        let quaternionOrder: String
        let rawSamplesInterpolated: Bool
        let recordedStreams: [String]
        let streams: [String: MotionStream]
    }

    struct MotionStream: Codable, Equatable {
        let unit: String
        let referenceFrame: String
    }

    struct UDPSummary: Codable, Equatable {
        let targetHost: String
        let targetPort: Int
        let configuredBitrateBitsPerSecond: Int
        let datagramBytes: Int
        let attemptedPacketCount: Int
        let successfulPacketCount: Int
        let failedPacketCount: Int
        let achievedBitrateBitsPerSecond: Double
    }

    struct SessionFile: Codable, Equatable {
        let role: String
        let path: String
        let bytes: Int64
        let sha256: String
    }
}

struct AssemblyRecord: Codable, Equatable {
    static let schemaVersion = "1.0.0"

    let schemaVersion: String
    let phoneAssemblyID: String
    let recordedAt: String
    let notes: String
}

struct RoomScanStatistics: Equatable {
    var arFrameCount = 0
    var videoFrameCount = 0
    var videoDroppedFrameCount = 0
    var faceAnchorSampleCount = 0
    var videoWidth: Int?
    var videoHeight: Int?
    var sourcePixelFormatFourCC: String?
}

struct MotionStatistics: Equatable {
    var sampleCount = 0
    var samplesBySensor: [String: Int] = [:]
}

struct VideoSampleIndexer: Equatable {
    private(set) var nextSampleID = 0

    mutating func recordAppend(success: Bool) -> Int? {
        guard success else { return nil }
        defer { nextSampleID += 1 }
        return nextSampleID
    }
}

struct SessionValidationReport: Codable, Equatable {
    static let schemaVersion = "1.0.0"

    let schemaVersion: String
    let sessionID: String
    let generatedAt: String
    let passed: Bool
    let errors: [String]
    let warnings: [String]
    let statistics: Statistics

    struct Statistics: Codable, Equatable {
        let durationSeconds: TimeInterval
        let videoBytes: Int64
        let arFrameCount: Int
        let videoFrameCount: Int
        let videoDroppedFrameCount: Int
        let videoMappingMissingRate: Double
        let arTimestampGapMaximumSeconds: TimeInterval
        let trackingStateCounts: [String: Int]
        let imuSampleCount: Int
        let imuSamplesBySensor: [String: Int]
        let imuEstimatedRatesHz: [String: Double]
        let faceAnchorSampleCount: Int
        let faceTrackedSampleCount: Int
        let faceTrackedRatio: Double
        let eventCount: Int
        let udpPacketCount: Int
        let udpSuccessfulPacketCount: Int
        let udpFailedPacketCount: Int
        let udpSequenceGapCount: Int
        let udpAchievedBitrateBitsPerSecond: Double
    }
}

enum SessionJSON {
    static func encode<T: Encodable>(_ value: T) throws -> Data {
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
        return try encoder.encode(value)
    }

    static func write<T: Encodable>(_ value: T, to url: URL) throws {
        try encode(value).write(to: url, options: .atomic)
    }
}
