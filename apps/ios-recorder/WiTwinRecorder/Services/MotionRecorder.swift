import CoreMotion
import Foundation

enum MotionRecorderError: LocalizedError {
    case noMotionSensors

    var errorDescription: String? {
        switch self {
        case .noMotionSensors:
            return "当前设备没有可用的 CoreMotion 数据流。"
        }
    }
}

final class MotionRecorder {
    typealias ErrorHandler = (_ error: Error) -> Void

    private let manager = CMMotionManager()
    private let queue: OperationQueue = {
        let queue = OperationQueue()
        queue.name = "org.witwin.recorder.motion"
        queue.maxConcurrentOperationCount = 1
        queue.qualityOfService = .userInitiated
        return queue
    }()
    private let writer: CSVWriter
    private let errorHandler: ErrorHandler

    private var sampleID = 0
    private var statistics = MotionStatistics()
    private var didReportFatalError = false

    init(sessionDirectory: URL, errorHandler: @escaping ErrorHandler) throws {
        writer = try CSVWriter(
            url: sessionDirectory.appendingPathComponent("imu.csv"),
            header: [
                "timestamp_seconds",
                "sample_id",
                "sensor_type",
                "x",
                "y",
                "z",
                "w",
                "accuracy"
            ]
        )
        self.errorHandler = errorHandler
    }

    func start() throws {
        guard manager.isAccelerometerAvailable
                || manager.isGyroAvailable
                || manager.isDeviceMotionAvailable else {
            throw MotionRecorderError.noMotionSensors
        }

        manager.accelerometerUpdateInterval = 1.0 / 100.0
        manager.gyroUpdateInterval = 1.0 / 100.0
        manager.deviceMotionUpdateInterval = 1.0 / 100.0

        if manager.isAccelerometerAvailable {
            manager.startAccelerometerUpdates(to: queue) { [weak self] sample, error in
                guard let self else { return }
                if let error {
                    self.reportFatalErrorOnce(error)
                    return
                }
                guard let sample else { return }
                self.append(
                    timestamp: sample.timestamp,
                    type: "accelerometer",
                    x: sample.acceleration.x,
                    y: sample.acceleration.y,
                    z: sample.acceleration.z
                )
            }
        }

        if manager.isGyroAvailable {
            manager.startGyroUpdates(to: queue) { [weak self] sample, error in
                guard let self else { return }
                if let error {
                    self.reportFatalErrorOnce(error)
                    return
                }
                guard let sample else { return }
                self.append(
                    timestamp: sample.timestamp,
                    type: "gyroscope",
                    x: sample.rotationRate.x,
                    y: sample.rotationRate.y,
                    z: sample.rotationRate.z
                )
            }
        }

        if manager.isDeviceMotionAvailable {
            manager.startDeviceMotionUpdates(
                using: .xArbitraryZVertical,
                to: queue
            ) { [weak self] sample, error in
                guard let self else { return }
                if let error {
                    self.reportFatalErrorOnce(error)
                    return
                }
                guard let sample else { return }

                self.append(
                    timestamp: sample.timestamp,
                    type: "device_motion_user_acceleration",
                    x: sample.userAcceleration.x,
                    y: sample.userAcceleration.y,
                    z: sample.userAcceleration.z
                )
                self.append(
                    timestamp: sample.timestamp,
                    type: "device_motion_rotation_rate",
                    x: sample.rotationRate.x,
                    y: sample.rotationRate.y,
                    z: sample.rotationRate.z
                )
                self.append(
                    timestamp: sample.timestamp,
                    type: "device_motion_gravity",
                    x: sample.gravity.x,
                    y: sample.gravity.y,
                    z: sample.gravity.z
                )
                self.append(
                    timestamp: sample.timestamp,
                    type: "device_motion_attitude_quaternion",
                    x: sample.attitude.quaternion.x,
                    y: sample.attitude.quaternion.y,
                    z: sample.attitude.quaternion.z,
                    w: sample.attitude.quaternion.w
                )
                self.append(
                    timestamp: sample.timestamp,
                    type: "device_motion_magnetic_field",
                    x: sample.magneticField.field.x,
                    y: sample.magneticField.field.y,
                    z: sample.magneticField.field.z,
                    accuracy: Self.accuracy(sample.magneticField.accuracy)
                )
            }
        }
    }

    func stop(completion: @escaping (Result<MotionStatistics, Error>) -> Void) {
        manager.stopAccelerometerUpdates()
        manager.stopGyroUpdates()
        manager.stopDeviceMotionUpdates()

        queue.addOperation { [self] in
            do {
                try writer.close()
                completion(.success(statistics))
            } catch {
                completion(.failure(error))
            }
        }
    }

    private func append(
        timestamp: TimeInterval,
        type: String,
        x: Double,
        y: Double,
        z: Double,
        w: Double? = nil,
        accuracy: String = ""
    ) {
        do {
            try writer.append([
                Self.decimal(timestamp),
                String(sampleID),
                type,
                Self.decimal(x),
                Self.decimal(y),
                Self.decimal(z),
                w.map(Self.decimal) ?? "",
                accuracy
            ])
            sampleID += 1
            statistics.sampleCount += 1
            statistics.samplesBySensor[type, default: 0] += 1
        } catch {
            reportFatalErrorOnce(error)
        }
    }

    private func reportFatalErrorOnce(_ error: Error) {
        guard !didReportFatalError else { return }
        didReportFatalError = true
        errorHandler(error)
    }

    private static func accuracy(_ accuracy: CMMagneticFieldCalibrationAccuracy) -> String {
        switch accuracy {
        case .uncalibrated:
            return "uncalibrated"
        case .low:
            return "low"
        case .medium:
            return "medium"
        case .high:
            return "high"
        @unknown default:
            return "unknown"
        }
    }

    private static func decimal<T: BinaryFloatingPoint>(_ value: T) -> String {
        String(format: "%.9f", Double(value))
    }
}

