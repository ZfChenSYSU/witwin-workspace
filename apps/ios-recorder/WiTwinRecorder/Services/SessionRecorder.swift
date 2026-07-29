import AVFoundation
import CryptoKit
import Foundation
import UIKit

enum SessionRecorderError: LocalizedError {
    case cameraPermissionUnavailable
    case capabilityReportMissing
    case invalidAssemblyID
    case incompleteStop

    var errorDescription: String? {
        switch self {
        case .cameraPermissionUnavailable:
            return "未获得相机权限，无法开始 P1 采集。"
        case .capabilityReportMissing:
            return "未找到 capabilities.json。请先运行一次 P0 能力探针。"
        case .invalidAssemblyID:
            return "装配编号不能为空，且只能包含字母、数字、点、下划线和连字符。"
        case .incompleteStop:
            return "采集模块未能完整停止。"
        }
    }
}

@MainActor
final class SessionRecorder: ObservableObject {
    @Published private(set) var state: RecordingState = .idle
    @Published private(set) var statusMessage = "准备开始 P1 采集"
    @Published private(set) var elapsedSeconds: TimeInterval = 0
    @Published private(set) var lastSessionURL: URL?
    @Published private(set) var validationReport: SessionValidationReport?

    private var roomRecorder: RoomScanRecorder?
    private var motionRecorder: MotionRecorder?
    private var eventWriter: CSVWriter?
    private var sessionDirectory: URL?
    private var sessionID: String?
    private var phoneAssemblyID = ""
    private var createdAt = Date()
    private var startedMonotonic = 0.0
    private var availableCapacityAtStart: Int64?
    private var thermalAtStart = "unknown"
    private var maximumThermalState = ProcessInfo.ThermalState.nominal
    private var elapsedTimer: Timer?
    private var stopReason = "user"
    private var stopStatus = "completed"
    private var pendingRoomStatistics: RoomScanStatistics?
    private var pendingMotionStatistics: MotionStatistics?
    private var pendingStopError: Error?
    private var waitingForRoomStop = false
    private var waitingForMotionStop = false

    var isBusy: Bool {
        state == .preparing || state == .recording || state == .stopping
    }

    var canStart: Bool {
        !isBusy
    }

    var canStop: Bool {
        state == .recording
    }

    func start(phoneAssemblyID: String) {
        guard canStart else { return }
        state = .preparing
        statusMessage = "正在准备会话目录与采集模块…"
        validationReport = nil
        lastSessionURL = nil

        Task { @MainActor in
            do {
                let sanitizedAssemblyID = try Self.validateAssemblyID(phoneAssemblyID)
                guard await Self.requestCameraAuthorizationIfNeeded() else {
                    throw SessionRecorderError.cameraPermissionUnavailable
                }
                try prepareAndStart(phoneAssemblyID: sanitizedAssemblyID)
            } catch {
                failBeforeRecording(error)
            }
        }
    }

    func markEvent(_ detail: String = "manual marker") {
        guard state == .recording else { return }
        appendEvent(type: "manual_marker", detail: detail)
        statusMessage = "已记录人工事件标记"
    }

    func stop(reason: String = "user", status: String = "completed") {
        guard state == .recording else { return }
        state = .stopping
        statusMessage = "正在停止并封装 session…"
        stopReason = reason
        stopStatus = status
        elapsedTimer?.invalidate()
        elapsedTimer = nil
        UIApplication.shared.isIdleTimerDisabled = false
        appendEvent(type: "session_stopping", detail: reason)

        pendingRoomStatistics = nil
        pendingMotionStatistics = nil
        pendingStopError = nil
        waitingForRoomStop = roomRecorder != nil
        waitingForMotionStop = motionRecorder != nil

        roomRecorder?.stop { [weak self] result in
            Task { @MainActor in
                guard let self else { return }
                self.waitingForRoomStop = false
                switch result {
                case .success(let statistics):
                    self.pendingRoomStatistics = statistics
                case .failure(let error):
                    self.pendingStopError = error
                }
                self.finishStopIfReady()
            }
        }
        motionRecorder?.stop { [weak self] result in
            Task { @MainActor in
                guard let self else { return }
                self.waitingForMotionStop = false
                switch result {
                case .success(let statistics):
                    self.pendingMotionStatistics = statistics
                case .failure(let error):
                    self.pendingStopError = error
                }
                self.finishStopIfReady()
            }
        }

        finishStopIfReady()
    }

    func handleAppBecameInactive() {
        if state == .recording {
            stop(reason: "app_became_inactive", status: "interrupted")
        }
    }

    private func prepareAndStart(phoneAssemblyID: String) throws {
        let documents = try FileManager.default.url(
            for: .documentDirectory,
            in: .userDomainMask,
            appropriateFor: nil,
            create: true
        )
        let capabilitiesSource = documents.appendingPathComponent("capabilities.json")
        guard FileManager.default.fileExists(atPath: capabilitiesSource.path) else {
            throw SessionRecorderError.capabilityReportMissing
        }

        let sessionsRoot = documents.appendingPathComponent("Sessions", isDirectory: true)
        try FileManager.default.createDirectory(
            at: sessionsRoot,
            withIntermediateDirectories: true
        )
        let identity = try Self.makeUniqueSessionIdentity(in: sessionsRoot)
        let directory = sessionsRoot.appendingPathComponent(identity, isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: false)
        try FileManager.default.copyItem(
            at: capabilitiesSource,
            to: directory.appendingPathComponent("capabilities.json")
        )

        createdAt = Date()
        startedMonotonic = ProcessInfo.processInfo.systemUptime
        availableCapacityAtStart = Self.availableCapacity(for: directory)
        thermalAtStart = Self.thermalDescription(ProcessInfo.processInfo.thermalState)
        maximumThermalState = ProcessInfo.processInfo.thermalState
        self.phoneAssemblyID = phoneAssemblyID
        sessionID = identity
        sessionDirectory = directory

        let assembly = AssemblyRecord(
            schemaVersion: AssemblyRecord.schemaVersion,
            phoneAssemblyID: phoneAssemblyID,
            recordedAt: ISO8601Timestamp.string(from: createdAt),
            notes: "固定手机、保护壳、夹持位置、方向与稳定器配置后复用此编号。"
        )
        try SessionJSON.write(
            assembly,
            to: directory.appendingPathComponent("assembly.json")
        )
        eventWriter = try CSVWriter(
            url: directory.appendingPathComponent("events.csv"),
            header: [
                "timestamp_seconds",
                "wall_time",
                "event_type",
                "detail"
            ]
        )
        try writeProvisionalMetadata(directory: directory, status: "recording")

        let errorHandler: (Error) -> Void = { [weak self] error in
            Task { @MainActor in
                guard let self, self.state == .recording else { return }
                self.appendEvent(type: "fatal_capture_error", detail: error.localizedDescription)
                self.stop(reason: error.localizedDescription, status: "failed")
            }
        }
        let eventHandler: RoomScanRecorder.EventHandler = { [weak self] type, detail, timestamp in
            Task { @MainActor in
                self?.appendEvent(type: type, detail: detail, timestamp: timestamp)
            }
        }

        let room = try RoomScanRecorder(
            sessionDirectory: directory,
            eventHandler: eventHandler,
            errorHandler: errorHandler
        )
        let motion = try MotionRecorder(
            sessionDirectory: directory,
            errorHandler: errorHandler
        )
        roomRecorder = room
        motionRecorder = motion

        try motion.start()
        do {
            try room.start()
        } catch {
            motion.stop { _ in }
            throw error
        }

        appendEvent(type: "session_started", detail: "phone_only_p1")
        state = .recording
        statusMessage = "正在同步采集后置视频、ARKit、IMU 与人脸锚点"
        elapsedSeconds = 0
        UIApplication.shared.isIdleTimerDisabled = true
        startElapsedTimer()
    }

    private func finishStopIfReady() {
        guard state == .stopping else { return }
        guard !waitingForRoomStop, !waitingForMotionStop else { return }
        guard let directory = sessionDirectory, let identity = sessionID else {
            completeWithFailure(SessionRecorderError.incompleteStop)
            return
        }

        if let pendingStopError {
            stopStatus = "failed"
            appendEvent(type: "stop_error", detail: pendingStopError.localizedDescription)
        }
        appendEvent(type: "session_stopped", detail: stopReason)
        do {
            try eventWriter?.close()
            eventWriter = nil
            let endedMonotonic = ProcessInfo.processInfo.systemUptime
            elapsedSeconds = max(0, endedMonotonic - startedMonotonic)

            let coreFileNames = [
                "capabilities.json",
                "assembly.json",
                "rear_video.mov",
                "ar_frames.csv",
                "face_anchors.csv",
                "imu.csv",
                "events.csv"
            ]
            let descriptors = try coreFileNames.compactMap { name -> SessionMetadata.SessionFile? in
                let url = directory.appendingPathComponent(name)
                guard FileManager.default.fileExists(atPath: url.path) else { return nil }
                return try Self.fileDescriptor(for: url, role: Self.fileRole(name))
            }

            var finalStatus = stopStatus
            try writeMetadata(
                directory: directory,
                status: finalStatus,
                endedMonotonic: endedMonotonic,
                files: descriptors
            )

            var report = try SessionIntegrityValidator.validate(
                sessionID: identity,
                directory: directory
            )
            if !report.passed, finalStatus == "completed" {
                finalStatus = "validation_failed"
                try writeMetadata(
                    directory: directory,
                    status: finalStatus,
                    endedMonotonic: endedMonotonic,
                    files: descriptors
                )
                report = try SessionIntegrityValidator.validate(
                    sessionID: identity,
                    directory: directory
                )
            }
            try SessionJSON.write(
                report,
                to: directory.appendingPathComponent("validation_report.json")
            )
            try Self.writeChecksums(in: directory)
            try Self.verifyChecksums(in: directory)

            validationReport = report
            lastSessionURL = directory
            if finalStatus == "completed", report.passed, pendingStopError == nil {
                state = .completed
                statusMessage = "P1 session 完成，自动完整性检查通过"
            } else {
                state = .failed
                let detail = pendingStopError?.localizedDescription
                    ?? report.errors.first
                    ?? finalStatus
                statusMessage = "session 已封装，但未通过：\(detail)"
            }
        } catch {
            completeWithFailure(error)
        }

        roomRecorder = nil
        motionRecorder = nil
    }

    private func writeProvisionalMetadata(directory: URL, status: String) throws {
        try writeMetadata(
            directory: directory,
            status: status,
            endedMonotonic: startedMonotonic,
            files: []
        )
    }

    private func writeMetadata(
        directory: URL,
        status: String,
        endedMonotonic: TimeInterval,
        files: [SessionMetadata.SessionFile]
    ) throws {
        guard let identity = sessionID else {
            throw SessionRecorderError.incompleteStop
        }
        let room = pendingRoomStatistics ?? RoomScanStatistics()
        let motion = pendingMotionStatistics ?? MotionStatistics()
        let metadata = SessionMetadata(
            schemaVersion: SessionMetadata.schemaVersion,
            sessionID: identity,
            captureStage: .phoneOnlyP1,
            createdAt: ISO8601Timestamp.string(from: createdAt),
            completedAt: ISO8601Timestamp.string(from: Date()),
            status: status,
            devices: .init(
                phone: .init(
                    model: UIDevice.current.model,
                    modelIdentifier: Self.modelIdentifier(),
                    osVersion: UIDevice.current.systemVersion,
                    appVersion: Bundle.main.object(
                        forInfoDictionaryKey: "CFBundleShortVersionString"
                    ) as? String ?? "unknown",
                    appBuild: Bundle.main.object(
                        forInfoDictionaryKey: "CFBundleVersion"
                    ) as? String ?? "unknown"
                )
            ),
            assembly: .init(phoneAssemblyID: phoneAssemblyID),
            timebases: .init(
                phone: .init(clock: "mach_continuous_time_seconds", unit: "s")
            ),
            coordinateConvention: "schemas/session-format/coordinate_frames.md",
            capture: .init(
                startedMonotonicSeconds: startedMonotonic,
                endedMonotonicSeconds: endedMonotonic,
                durationSeconds: max(0, endedMonotonic - startedMonotonic),
                videoFrameCount: room.videoFrameCount,
                videoDroppedFrameCount: room.videoDroppedFrameCount,
                arFrameCount: room.arFrameCount,
                faceAnchorSampleCount: room.faceAnchorSampleCount,
                imuSampleCount: motion.sampleCount,
                thermalStateAtStart: thermalAtStart,
                maximumThermalState: Self.thermalDescription(maximumThermalState),
                thermalStateAtEnd: Self.thermalDescription(ProcessInfo.processInfo.thermalState),
                availableCapacityBytesAtStart: availableCapacityAtStart,
                availableCapacityBytesAtEnd: Self.availableCapacity(for: directory)
            ),
            files: files
        )
        try SessionJSON.write(
            metadata,
            to: directory.appendingPathComponent("metadata.json")
        )
    }

    private func appendEvent(
        type: String,
        detail: String,
        timestamp: TimeInterval = ProcessInfo.processInfo.systemUptime
    ) {
        do {
            try eventWriter?.append([
                Self.decimal(timestamp),
                ISO8601Timestamp.string(from: Date()),
                type,
                detail
            ])
        } catch {
            pendingStopError = error
        }
    }

    private func startElapsedTimer() {
        elapsedTimer?.invalidate()
        elapsedTimer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in
            Task { @MainActor in
                guard let self, self.state == .recording else { return }
                self.elapsedSeconds = ProcessInfo.processInfo.systemUptime - self.startedMonotonic
                let thermal = ProcessInfo.processInfo.thermalState
                if Self.thermalRank(thermal) > Self.thermalRank(self.maximumThermalState) {
                    self.maximumThermalState = thermal
                    self.appendEvent(
                        type: "thermal_state_changed",
                        detail: Self.thermalDescription(thermal)
                    )
                }
                if thermal == .critical {
                    self.stop(reason: "thermal_state_critical", status: "failed")
                }
            }
        }
    }

    private func failBeforeRecording(_ error: Error) {
        UIApplication.shared.isIdleTimerDisabled = false
        elapsedTimer?.invalidate()
        elapsedTimer = nil
        state = .failed
        statusMessage = error.localizedDescription
        if let directory = sessionDirectory {
            lastSessionURL = directory
        }
        roomRecorder = nil
        motionRecorder = nil
        try? eventWriter?.close()
        eventWriter = nil
    }

    private func completeWithFailure(_ error: Error) {
        UIApplication.shared.isIdleTimerDisabled = false
        state = .failed
        statusMessage = "session 封装失败：\(error.localizedDescription)"
        lastSessionURL = sessionDirectory
    }
}

private extension SessionRecorder {
    static func validateAssemblyID(_ input: String) throws -> String {
        let trimmed = input.trimmingCharacters(in: .whitespacesAndNewlines)
        let pattern = "^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"
        guard trimmed.range(of: pattern, options: .regularExpression) != nil else {
            throw SessionRecorderError.invalidAssemblyID
        }
        return trimmed
    }

    static func requestCameraAuthorizationIfNeeded() async -> Bool {
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized:
            return true
        case .notDetermined:
            return await withCheckedContinuation { continuation in
                AVCaptureDevice.requestAccess(for: .video) { granted in
                    continuation.resume(returning: granted)
                }
            }
        case .denied, .restricted:
            return false
        @unknown default:
            return false
        }
    }

    static func makeUniqueSessionIdentity(in root: URL) throws -> String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.timeZone = .current
        formatter.dateFormat = "'session_'yyyyMMdd_HHmmss"
        let base = formatter.string(from: Date())
        var identity = base
        var suffix = 1
        while FileManager.default.fileExists(
            atPath: root.appendingPathComponent(identity).path
        ) {
            identity = "\(base)_\(suffix)"
            suffix += 1
        }
        return identity
    }

    static func fileDescriptor(
        for url: URL,
        role: String
    ) throws -> SessionMetadata.SessionFile {
        let attributes = try FileManager.default.attributesOfItem(atPath: url.path)
        let bytes = (attributes[.size] as? NSNumber)?.int64Value ?? 0
        return .init(
            role: role,
            path: url.lastPathComponent,
            bytes: bytes,
            sha256: try sha256(url)
        )
    }

    static func writeChecksums(in directory: URL) throws {
        let files = try FileManager.default.contentsOfDirectory(
            at: directory,
            includingPropertiesForKeys: [.isRegularFileKey],
            options: [.skipsHiddenFiles]
        )
        let lines = try files
            .filter { $0.lastPathComponent != "checksums.sha256" }
            .filter { (try? $0.resourceValues(forKeys: [.isRegularFileKey]).isRegularFile) == true }
            .sorted { $0.lastPathComponent < $1.lastPathComponent }
            .map { "\(try sha256($0))  \($0.lastPathComponent)" }
        let content = lines.joined(separator: "\n") + "\n"
        try Data(content.utf8).write(
            to: directory.appendingPathComponent("checksums.sha256"),
            options: .atomic
        )
    }

    static func verifyChecksums(in directory: URL) throws {
        let manifestURL = directory.appendingPathComponent("checksums.sha256")
        let lines = try String(contentsOf: manifestURL, encoding: .utf8)
            .split(whereSeparator: \.isNewline)
        for line in lines {
            let parts = line.split(separator: " ", omittingEmptySubsequences: true)
            guard parts.count == 2 else {
                throw CocoaError(.fileReadCorruptFile)
            }
            let expected = String(parts[0])
            let name = String(parts[1])
            let actual = try sha256(directory.appendingPathComponent(name))
            guard expected == actual else {
                throw CocoaError(.fileReadCorruptFile)
            }
        }
    }

    static func sha256(_ url: URL) throws -> String {
        let handle = try FileHandle(forReadingFrom: url)
        defer { try? handle.close() }
        var hasher = SHA256()
        while let data = try handle.read(upToCount: 1_048_576), !data.isEmpty {
            hasher.update(data: data)
        }
        return hasher.finalize().map { String(format: "%02x", $0) }.joined()
    }

    static func fileRole(_ name: String) -> String {
        switch name {
        case "capabilities.json": return "device_capabilities"
        case "assembly.json": return "phone_assembly"
        case "rear_video.mov": return "rear_camera_video"
        case "ar_frames.csv": return "arkit_frames"
        case "face_anchors.csv": return "face_anchors"
        case "imu.csv": return "core_motion"
        case "events.csv": return "capture_events"
        default: return "other"
        }
    }

    static func modelIdentifier() -> String {
        var size = 0
        sysctlbyname("hw.machine", nil, &size, nil, 0)
        var value = [CChar](repeating: 0, count: size)
        sysctlbyname("hw.machine", &value, &size, nil, 0)
        return String(cString: value)
    }

    static func availableCapacity(for url: URL) -> Int64? {
        try? url.resourceValues(
            forKeys: [.volumeAvailableCapacityForImportantUsageKey]
        ).volumeAvailableCapacityForImportantUsage
    }

    static func thermalRank(_ state: ProcessInfo.ThermalState) -> Int {
        switch state {
        case .nominal: return 0
        case .fair: return 1
        case .serious: return 2
        case .critical: return 3
        @unknown default: return 4
        }
    }

    static func thermalDescription(_ state: ProcessInfo.ThermalState) -> String {
        switch state {
        case .nominal: return "nominal"
        case .fair: return "fair"
        case .serious: return "serious"
        case .critical: return "critical"
        @unknown default: return "unknown"
        }
    }

    static func decimal<T: BinaryFloatingPoint>(_ value: T) -> String {
        String(format: "%.9f", Double(value))
    }
}

