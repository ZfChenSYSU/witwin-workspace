import ARKit
import AVFoundation
import CoreMotion
import Foundation
import simd
import UIKit

@MainActor
final class FaceDistanceService: NSObject, ObservableObject {
    @Published private(set) var isRunning = false
    @Published private(set) var statusMessage = "尚未启动"
    @Published private(set) var distanceMeters: Double?
    @Published private(set) var relativePositionMeters: SIMD3<Float>?
    @Published private(set) var trackingState = "unknown"

    private let session = ARSession()
    private var lastFileWriteUptimeNanoseconds: UInt64 = 0
    private var latestFaceTransform: simd_float4x4?
    private var latestFaceTracked = false
    private var latestFaceTimestamp: TimeInterval?

    override init() {
        super.init()
        session.delegate = self
        session.delegateQueue = .main
    }

    func start() {
        guard !isRunning else { return }
        guard ARWorldTrackingConfiguration.isSupported,
              ARWorldTrackingConfiguration.supportsUserFaceTracking else {
            statusMessage = "当前设备不支持世界跟踪 + 用户人脸跟踪"
            return
        }

        let configuration = ARWorldTrackingConfiguration()
        configuration.userFaceTrackingEnabled = true
        distanceMeters = nil
        relativePositionMeters = nil
        latestFaceTransform = nil
        latestFaceTracked = false
        latestFaceTimestamp = nil
        trackingState = "等待 ARFrame / ARFaceAnchor"
        statusMessage = "正在实时测距…请保持人脸正对前置摄像头"
        isRunning = true
        session.run(configuration, options: [.resetTracking, .removeExistingAnchors])
    }

    func stop() {
        guard isRunning else { return }
        session.pause()
        isRunning = false
        statusMessage = "已停止"
    }

    private func update(faceTransform: simd_float4x4, cameraTransform: simd_float4x4,
                        isTracked: Bool, timestamp: TimeInterval) {
        let facePosition = SIMD3<Float>(
            faceTransform.columns.3.x,
            faceTransform.columns.3.y,
            faceTransform.columns.3.z
        )
        let cameraPosition = SIMD3<Float>(
            cameraTransform.columns.3.x,
            cameraTransform.columns.3.y,
            cameraTransform.columns.3.z
        )
        let relativePosition = facePosition - cameraPosition
        let distance = simd_length(relativePosition)

        trackingState = isTracked ? "normal" : "face_not_tracked"
        relativePositionMeters = relativePosition
        distanceMeters = isTracked ? Double(distance) : nil
        statusMessage = isTracked ? "实时测距中" : "人脸跟踪暂时丢失"

        latestFaceTransform = faceTransform
        latestFaceTracked = isTracked
        latestFaceTimestamp = timestamp
        persistSnapshot(cameraTransform: cameraTransform, timestamp: timestamp)
    }

    private func persistSnapshot(cameraTransform: simd_float4x4, timestamp: TimeInterval) {
        let now = DispatchTime.now().uptimeNanoseconds
        guard now - lastFileWriteUptimeNanoseconds >= 500_000_000 else { return }
        lastFileWriteUptimeNanoseconds = now
        var snapshot: [String: Any] = [
            "timestamp_seconds": timestamp,
            "ar_frame_received": true,
            "face_anchor_seen": latestFaceTransform != nil,
            "face_anchor_is_tracked": latestFaceTracked,
            "camera_tracking_state": trackingState,
            "coordinate_definition": "norm(arkit_world_T_face_anchor.translation - arkit_world_T_rear_camera.translation)",
            "reference_warning": "未完成前摄像头—机身外参标定；这是人脸锚点中心到后置相机参考点的 ARKit 近似距离，不是胸腔真值。"
        ]
        if let faceTransform = latestFaceTransform, latestFaceTracked {
            let facePosition = SIMD3<Float>(
                faceTransform.columns.3.x,
                faceTransform.columns.3.y,
                faceTransform.columns.3.z
            )
            let cameraPosition = SIMD3<Float>(
                cameraTransform.columns.3.x,
                cameraTransform.columns.3.y,
                cameraTransform.columns.3.z
            )
            let relativePosition = facePosition - cameraPosition
            snapshot["distance_meters"] = Double(simd_length(relativePosition))
            snapshot["relative_face_position_from_rear_camera_meters"] = [
                Double(relativePosition.x), Double(relativePosition.y), Double(relativePosition.z)
            ]
            snapshot["face_anchor_timestamp_seconds"] = latestFaceTimestamp ?? timestamp
        }
        guard JSONSerialization.isValidJSONObject(snapshot),
              let data = try? JSONSerialization.data(withJSONObject: snapshot, options: [.sortedKeys]) else {
            return
        }
        if let distance = snapshot["distance_meters"] as? Double {
            print(String(format: "WITWIN_FACE_DISTANCE distance_m=%.6f tracked=%@ ar_camera_state=%@", distance, latestFaceTracked ? "true" : "false", trackingState))
        } else {
            print("WITWIN_FACE_DISTANCE distance_m=nil face_anchor_seen=\(latestFaceTransform != nil) tracked=\(latestFaceTracked) ar_camera_state=\(trackingState)")
        }
        guard let documents = try? FileManager.default.url(
            for: .documentDirectory,
            in: .userDomainMask,
            appropriateFor: nil,
            create: true
        ) else { return }
        try? data.write(
            to: documents.appendingPathComponent("face_distance_live.json"),
            options: [.atomic]
        )
    }
}

extension FaceDistanceService: ARSessionDelegate {
    nonisolated func session(_ session: ARSession, didUpdate frame: ARFrame) {
        Task { @MainActor [weak self] in
            guard let self else { return }
            self.trackingState = Self.trackingStateDescription(frame.camera.trackingState)
            self.persistSnapshot(cameraTransform: frame.camera.transform, timestamp: frame.timestamp)
        }
    }

    nonisolated func session(_ session: ARSession, didAdd anchors: [ARAnchor]) {
        processFaceAnchors(anchors, session: session)
    }

    nonisolated func session(_ session: ARSession, didUpdate anchors: [ARAnchor]) {
        processFaceAnchors(anchors, session: session)
    }

    nonisolated private func processFaceAnchors(_ anchors: [ARAnchor], session: ARSession) {
        guard let faceAnchor = anchors.compactMap({ $0 as? ARFaceAnchor }).first,
              let frame = session.currentFrame else { return }
        let faceTransform = faceAnchor.transform
        let cameraTransform = frame.camera.transform
        let isTracked = faceAnchor.isTracked
        let timestamp = frame.timestamp
        Task { @MainActor [weak self] in
            self?.update(
                faceTransform: faceTransform,
                cameraTransform: cameraTransform,
                isTracked: isTracked,
                timestamp: timestamp
            )
        }
    }

    nonisolated func session(_ session: ARSession, didFailWithError error: Error) {
        Task { @MainActor [weak self] in
            self?.statusMessage = "ARSession 失败：\(error.localizedDescription)"
            self?.isRunning = false
        }
    }

    private static func trackingStateDescription(_ state: ARCamera.TrackingState) -> String {
        switch state {
        case .normal: return "normal"
        case .notAvailable: return "not_available"
        case .limited(let reason): return "limited_\(String(describing: reason))"
        }
    }
}

@MainActor
final class CapabilityProbeService: NSObject, ObservableObject {
    @Published private(set) var isRunning = false
    @Published private(set) var statusMessage = "尚未运行"
    @Published private(set) var report: CapabilityReport?
    @Published private(set) var reportFileURL: URL?

    private let session = ARSession()
    private let motionManager = CMMotionManager()
    private var timeoutWorkItem: DispatchWorkItem?
    private var didFinishCurrentRun = false
    private var requestedUserFaceTracking = false
    private var faceAnchorObserved = false
    private var faceAnchorFrameTimestamp: TimeInterval?
    private var faceAnchorTransform: simd_float4x4?

    override init() {
        super.init()
        session.delegate = self
        session.delegateQueue = .main
    }

    func run() {
        guard !isRunning else { return }

        isRunning = true
        statusMessage = "正在检查权限与设备能力…"
        report = nil
        reportFileURL = nil
        didFinishCurrentRun = false
        requestedUserFaceTracking = false
        faceAnchorObserved = false
        faceAnchorFrameTimestamp = nil
        faceAnchorTransform = nil

        Task { @MainActor in
            let cameraAllowed = await requestCameraAuthorizationIfNeeded()
            beginARValidation(cameraAllowed: cameraAllowed)
        }
    }

    private func requestCameraAuthorizationIfNeeded() async -> Bool {
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

    private func beginARValidation(cameraAllowed: Bool) {
        guard cameraAllowed else {
            finish(frame: nil, status: "camera_permission_unavailable",
                   notes: ["未获得相机权限，无法启动 ARSession。"])
            return
        }

        guard ARWorldTrackingConfiguration.isSupported else {
            finish(frame: nil, status: "world_tracking_unsupported",
                   notes: physicalDeviceNotes(appending: "当前运行环境不支持 ARWorldTrackingConfiguration。"))
            return
        }

        let configuration = ARWorldTrackingConfiguration()
        requestedUserFaceTracking = ARWorldTrackingConfiguration.supportsUserFaceTracking
        if requestedUserFaceTracking {
            configuration.userFaceTrackingEnabled = true
        }

        statusMessage = requestedUserFaceTracking
            ? "正在等待后置世界跟踪和前置人脸跟踪帧…"
            : "正在等待 ARKit 世界跟踪帧…"

        session.run(configuration, options: [.resetTracking, .removeExistingAnchors])

        let workItem = DispatchWorkItem { [weak self] in
            guard let self, !self.didFinishCurrentRun else { return }
            let frame = self.session.currentFrame
            let status: String
            let note: String
            if frame == nil {
                status = "ar_frame_timeout"
                note = "等待 ARFrame 超时；请检查相机权限和设备支持状态。"
            } else if let frame, !Self.isTrackingNormal(frame.camera.trackingState) {
                status = "tracking_not_normal_timeout"
                note = "已收到 ARFrame，但世界跟踪未在限定时间内达到 normal。"
            } else if self.requestedUserFaceTracking && !self.faceAnchorObserved {
                status = "face_anchor_timeout"
                note = "已收到 ARFrame，但等待 ARFaceAnchor 超时；请确认人脸正对前置摄像头。"
            } else {
                status = self.faceAnchorObserved
                    ? "ar_frame_and_face_anchor_received"
                    : "ar_frame_received"
                note = "世界跟踪已达到 normal。"
            }
            self.finish(
                frame: frame,
                status: status,
                notes: self.physicalDeviceNotes(appending: note)
            )
        }
        timeoutWorkItem = workItem
        DispatchQueue.main.asyncAfter(deadline: .now() + 8, execute: workItem)
    }

    private func finish(frame: ARFrame?, status: String, notes: [String]) {
        guard !didFinishCurrentRun else { return }
        didFinishCurrentRun = true
        timeoutWorkItem?.cancel()
        timeoutWorkItem = nil
        session.pause()

        let completedReport = makeReport(frame: frame, status: status, notes: notes)
        report = completedReport

        do {
            let directory = try FileManager.default.url(
                for: .documentDirectory,
                in: .userDomainMask,
                appropriateFor: nil,
                create: true
            )
            reportFileURL = try CapabilityReportWriter.write(completedReport, to: directory)
            statusMessage = "完成：capabilities.json 已保存"
        } catch {
            statusMessage = "探针完成，但保存失败：\(error.localizedDescription)"
        }

        isRunning = false
    }

    private func makeReport(
        frame: ARFrame?,
        status: String,
        notes: [String]
    ) -> CapabilityReport {
        let capturedWidth = frame.map { CVPixelBufferGetWidth($0.capturedImage) }
        let capturedHeight = frame.map { CVPixelBufferGetHeight($0.capturedImage) }
        let imageResolution = frame?.camera.imageResolution

        return CapabilityReport(
            schemaVersion: CapabilityReport.schemaVersion,
            generatedAt: Self.iso8601Formatter.string(from: Date()),
            monotonicTimestampSeconds: ProcessInfo.processInfo.systemUptime,
            executionEnvironment: .init(
                isSimulator: Self.isSimulator,
                requiresPhysicalDeviceValidation: Self.isSimulator
            ),
            device: .init(
                modelName: UIDevice.current.model,
                modelIdentifier: Self.modelIdentifier(),
                systemName: UIDevice.current.systemName,
                systemVersion: UIDevice.current.systemVersion
            ),
            app: .init(
                version: Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "unknown",
                build: Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "unknown"
            ),
            arkit: .init(
                worldTrackingSupported: ARWorldTrackingConfiguration.isSupported,
                worldTrackingSupportsUserFaceTracking: ARWorldTrackingConfiguration.supportsUserFaceTracking,
                faceTrackingSupported: ARFaceTrackingConfiguration.isSupported
            ),
            camera: .init(
                authorizationStatus: Self.cameraAuthorizationDescription(),
                availableDevices: Self.cameraDevices(),
                capturedImageWidth: capturedWidth,
                capturedImageHeight: capturedHeight,
                imageResolutionWidth: imageResolution.map { Int($0.width) },
                imageResolutionHeight: imageResolution.map { Int($0.height) },
                intrinsics3x3RowMajor: frame.map { Self.rowMajor($0.camera.intrinsics) }
            ),
            motion: .init(
                authorizationStatus: Self.motionAuthorizationDescription(),
                accelerometerAvailable: motionManager.isAccelerometerAvailable,
                gyroAvailable: motionManager.isGyroAvailable,
                deviceMotionAvailable: motionManager.isDeviceMotionAvailable,
                magnetometerAvailable: motionManager.isMagnetometerAvailable
            ),
            storage: Self.storageCapabilities(),
            thermalState: Self.thermalStateDescription(ProcessInfo.processInfo.thermalState),
            runtimeValidation: .init(
                status: status,
                arFrameReceived: frame != nil,
                arFrameTimestampSeconds: frame?.timestamp,
                trackingState: frame.map { Self.trackingStateDescription($0.camera.trackingState) },
                worldTransform4x4RowMajor: frame.map { Self.rowMajor($0.camera.transform) },
                userFaceTrackingEnabled: requestedUserFaceTracking,
                faceAnchorObserved: faceAnchorObserved,
                faceAnchorFrameTimestampSeconds: faceAnchorFrameTimestamp,
                faceAnchorTransform4x4RowMajor: faceAnchorTransform.map(Self.rowMajor),
                notes: notes
            )
        )
    }

    private func physicalDeviceNotes(appending note: String? = nil) -> [String] {
        var notes = [String]()
        if Self.isSimulator {
            notes.append("当前结果来自模拟器，不能作为 iPhone 11 Pro 的 ARKit、TrueDepth、摄像头或 CoreMotion 能力证据。")
        }
        if let note {
            notes.append(note)
        }
        if requestedUserFaceTracking && !faceAnchorObserved {
            notes.append("本次运行尚未观察到 ARFaceAnchor；需要在 iPhone 11 Pro 真机上面对前置摄像头复测。")
        }
        return notes
    }
}

extension CapabilityProbeService: ARSessionDelegate {
    nonisolated func session(_ session: ARSession, didUpdate frame: ARFrame) {
        Task { @MainActor [weak self] in
            guard let self, !self.didFinishCurrentRun else { return }
            guard Self.isTrackingNormal(frame.camera.trackingState) else {
                self.statusMessage = "已收到 ARFrame，正在等待世界跟踪达到 normal…"
                return
            }
            if self.requestedUserFaceTracking && !self.faceAnchorObserved {
                self.statusMessage = "已收到 ARFrame，正在等待 ARFaceAnchor…"
                return
            }
            self.finish(
                frame: frame,
                status: self.faceAnchorObserved
                    ? "ar_frame_and_face_anchor_received"
                    : "ar_frame_received",
                notes: self.physicalDeviceNotes()
            )
        }
    }

    nonisolated func session(_ session: ARSession, didAdd anchors: [ARAnchor]) {
        guard let faceAnchor = anchors.compactMap({ $0 as? ARFaceAnchor }).first else { return }
        let transform = faceAnchor.transform
        let frame = session.currentFrame
        Task { @MainActor [weak self] in
            guard let self, !self.didFinishCurrentRun else { return }
            self.faceAnchorObserved = true
            self.faceAnchorTransform = transform
            self.faceAnchorFrameTimestamp = frame?.timestamp
            if let frame, Self.isTrackingNormal(frame.camera.trackingState) {
                self.finish(
                    frame: frame,
                    status: "ar_frame_and_face_anchor_received",
                    notes: self.physicalDeviceNotes()
                )
            }
        }
    }

    nonisolated func session(_ session: ARSession, didUpdate anchors: [ARAnchor]) {
        guard let faceAnchor = anchors.compactMap({ $0 as? ARFaceAnchor }).first else { return }
        let transform = faceAnchor.transform
        let frameTimestamp = session.currentFrame?.timestamp
        Task { @MainActor [weak self] in
            guard let self, !self.didFinishCurrentRun else { return }
            self.faceAnchorObserved = true
            self.faceAnchorTransform = transform
            self.faceAnchorFrameTimestamp = frameTimestamp
        }
    }

    nonisolated func session(_ session: ARSession, didFailWithError error: Error) {
        Task { @MainActor [weak self] in
            guard let self, !self.didFinishCurrentRun else { return }
            self.finish(
                frame: session.currentFrame,
                status: "ar_session_failed",
                notes: self.physicalDeviceNotes(appending: error.localizedDescription)
            )
        }
    }
}

private extension CapabilityProbeService {
    static let iso8601Formatter: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter
    }()

    static var isSimulator: Bool {
        #if targetEnvironment(simulator)
        true
        #else
        false
        #endif
    }

    static func modelIdentifier() -> String {
        var size = 0
        sysctlbyname("hw.machine", nil, &size, nil, 0)
        var value = [CChar](repeating: 0, count: size)
        sysctlbyname("hw.machine", &value, &size, nil, 0)
        return String(cString: value)
    }

    static func cameraAuthorizationDescription() -> String {
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized: "authorized"
        case .denied: "denied"
        case .notDetermined: "not_determined"
        case .restricted: "restricted"
        @unknown default: "unknown"
        }
    }

    static func motionAuthorizationDescription() -> String {
        switch CMMotionActivityManager.authorizationStatus() {
        case .authorized: "authorized"
        case .denied: "denied"
        case .notDetermined: "not_determined"
        case .restricted: "restricted"
        @unknown default: "unknown"
        }
    }

    static func cameraDevices() -> [CapabilityReport.CameraDevice] {
        let discovery = AVCaptureDevice.DiscoverySession(
            deviceTypes: [
                .builtInWideAngleCamera,
                .builtInUltraWideCamera,
                .builtInTelephotoCamera,
                .builtInTrueDepthCamera
            ],
            mediaType: .video,
            position: .unspecified
        )
        return discovery.devices.map {
            .init(
                uniqueID: $0.uniqueID,
                localizedName: $0.localizedName,
                position: positionDescription($0.position),
                deviceType: $0.deviceType.rawValue
            )
        }
    }

    static func positionDescription(_ position: AVCaptureDevice.Position) -> String {
        switch position {
        case .back: "back"
        case .front: "front"
        case .unspecified: "unspecified"
        @unknown default: "unknown"
        }
    }

    static func storageCapabilities() -> CapabilityReport.StorageCapabilities {
        let documents = (try? FileManager.default.url(
            for: .documentDirectory,
            in: .userDomainMask,
            appropriateFor: nil,
            create: true
        )) ?? FileManager.default.temporaryDirectory
        let values = try? documents.resourceValues(forKeys: [
            .volumeAvailableCapacityKey,
            .volumeAvailableCapacityForImportantUsageKey
        ])
        return .init(
            documentsDirectory: documents.path,
            volumeAvailableCapacityBytes: values?.volumeAvailableCapacity.map(Int64.init),
            volumeAvailableCapacityForImportantUsageBytes: values?.volumeAvailableCapacityForImportantUsage
        )
    }

    static func thermalStateDescription(_ state: ProcessInfo.ThermalState) -> String {
        switch state {
        case .nominal: "nominal"
        case .fair: "fair"
        case .serious: "serious"
        case .critical: "critical"
        @unknown default: "unknown"
        }
    }

    static func trackingStateDescription(_ state: ARCamera.TrackingState) -> String {
        switch state {
        case .normal:
            "normal"
        case .notAvailable:
            "not_available"
        case .limited(let reason):
            "limited:\(trackingReasonDescription(reason))"
        }
    }

    static func isTrackingNormal(_ state: ARCamera.TrackingState) -> Bool {
        if case .normal = state {
            return true
        }
        return false
    }

    static func trackingReasonDescription(_ reason: ARCamera.TrackingState.Reason) -> String {
        switch reason {
        case .initializing: "initializing"
        case .excessiveMotion: "excessive_motion"
        case .insufficientFeatures: "insufficient_features"
        case .relocalizing: "relocalizing"
        @unknown default: "unknown"
        }
    }

    static func rowMajor(_ matrix: simd_float3x3) -> [Float] {
        (0..<3).flatMap { row in
            (0..<3).map { column in matrix[column][row] }
        }
    }

    static func rowMajor(_ matrix: simd_float4x4) -> [Float] {
        (0..<4).flatMap { row in
            (0..<4).map { column in matrix[column][row] }
        }
    }
}
