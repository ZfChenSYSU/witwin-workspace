import ARKit
import AVFoundation
import CoreMedia
import Foundation

enum RoomScanRecorderError: LocalizedError {
    case worldTrackingUnavailable
    case cannotCreateAssetWriter(String)
    case cannotStartAssetWriter(String)
    case videoAppendFailed(String)

    var errorDescription: String? {
        switch self {
        case .worldTrackingUnavailable:
            return "当前设备不支持 ARKit 世界跟踪。"
        case .cannotCreateAssetWriter(let detail):
            return "无法创建 HEVC 视频写入器：\(detail)"
        case .cannotStartAssetWriter(let detail):
            return "无法启动 HEVC 视频写入器：\(detail)"
        case .videoAppendFailed(let detail):
            return "视频帧写入失败：\(detail)"
        }
    }
}

final class RoomScanRecorder: NSObject {
    typealias EventHandler = (_ type: String, _ detail: String, _ timestamp: TimeInterval) -> Void
    typealias ErrorHandler = (_ error: Error) -> Void

    private let session = ARSession()
    private let recordingQueue = DispatchQueue(label: "org.witwin.recorder.arkit")
    private let videoURL: URL
    private let arWriter: CSVWriter
    private let faceWriter: CSVWriter
    private let eventHandler: EventHandler
    private let errorHandler: ErrorHandler

    private var assetWriter: AVAssetWriter?
    private var videoInput: AVAssetWriterInput?
    private var pixelBufferAdaptor: AVAssetWriterInputPixelBufferAdaptor?
    private var firstFrameTimestamp: TimeInterval?
    private var acceptingFrames = false
    private var frameID = 0
    private var faceTrackingActive = false
    private var didReportFatalError = false
    private var statistics = RoomScanStatistics()

    init(
        sessionDirectory: URL,
        eventHandler: @escaping EventHandler,
        errorHandler: @escaping ErrorHandler
    ) throws {
        videoURL = sessionDirectory.appendingPathComponent("rear_video.mov")
        arWriter = try CSVWriter(
            url: sessionDirectory.appendingPathComponent("ar_frames.csv"),
            header: Self.arHeader
        )
        faceWriter = try CSVWriter(
            url: sessionDirectory.appendingPathComponent("face_anchors.csv"),
            header: Self.faceHeader
        )
        self.eventHandler = eventHandler
        self.errorHandler = errorHandler
        super.init()
        session.delegate = self
        session.delegateQueue = recordingQueue
    }

    func start() throws {
        guard ARWorldTrackingConfiguration.isSupported else {
            throw RoomScanRecorderError.worldTrackingUnavailable
        }

        let configuration = ARWorldTrackingConfiguration()
        if ARWorldTrackingConfiguration.supportsUserFaceTracking {
            configuration.userFaceTrackingEnabled = true
        }
        configuration.worldAlignment = .gravity

        acceptingFrames = true
        session.run(configuration, options: [.resetTracking, .removeExistingAnchors])
        eventHandler(
            "arkit_started",
            configuration.userFaceTrackingEnabled
                ? "world_tracking_with_user_face_tracking"
                : "world_tracking_without_user_face_tracking",
            ProcessInfo.processInfo.systemUptime
        )
    }

    func stop(completion: @escaping (Result<RoomScanStatistics, Error>) -> Void) {
        session.pause()
        recordingQueue.async { [self] in
            acceptingFrames = false

            do {
                try arWriter.close()
                try faceWriter.close()
            } catch {
                completion(.failure(error))
                return
            }

            guard let assetWriter, let videoInput else {
                completion(.success(statistics))
                return
            }

            videoInput.markAsFinished()
            assetWriter.finishWriting { [self] in
                if assetWriter.status == .completed {
                    completion(.success(statistics))
                } else {
                    completion(.failure(
                        assetWriter.error
                            ?? RoomScanRecorderError.videoAppendFailed("AVAssetWriter 未正常完成。")
                    ))
                }
            }
        }
    }

    private func configureVideoIfNeeded(for pixelBuffer: CVPixelBuffer) throws {
        guard assetWriter == nil else { return }

        do {
            let writer = try AVAssetWriter(outputURL: videoURL, fileType: .mov)
            let width = CVPixelBufferGetWidth(pixelBuffer)
            let height = CVPixelBufferGetHeight(pixelBuffer)
            let settings: [String: Any] = [
                AVVideoCodecKey: AVVideoCodecType.hevc,
                AVVideoWidthKey: width,
                AVVideoHeightKey: height,
                AVVideoCompressionPropertiesKey: [
                    AVVideoAverageBitRateKey: 12_000_000,
                    AVVideoExpectedSourceFrameRateKey: 60,
                    AVVideoMaxKeyFrameIntervalKey: 120
                ]
            ]
            let input = AVAssetWriterInput(mediaType: .video, outputSettings: settings)
            input.expectsMediaDataInRealTime = true

            guard writer.canAdd(input) else {
                throw RoomScanRecorderError.cannotCreateAssetWriter(
                    "AVAssetWriter 不接受当前 HEVC 输入设置。"
                )
            }
            writer.add(input)

            let adaptor = AVAssetWriterInputPixelBufferAdaptor(
                assetWriterInput: input,
                sourcePixelBufferAttributes: nil
            )
            guard writer.startWriting() else {
                throw RoomScanRecorderError.cannotStartAssetWriter(
                    writer.error?.localizedDescription ?? "未知错误"
                )
            }
            writer.startSession(atSourceTime: .zero)
            assetWriter = writer
            videoInput = input
            pixelBufferAdaptor = adaptor
        } catch let error as RoomScanRecorderError {
            throw error
        } catch {
            throw RoomScanRecorderError.cannotCreateAssetWriter(error.localizedDescription)
        }
    }

    private func record(_ frame: ARFrame) {
        guard acceptingFrames else { return }

        do {
            try configureVideoIfNeeded(for: frame.capturedImage)
            if firstFrameTimestamp == nil {
                firstFrameTimestamp = frame.timestamp
            }

            let currentFrameID = frameID
            frameID += 1
            statistics.arFrameCount += 1

            let videoPTSSeconds = max(0, frame.timestamp - (firstFrameTimestamp ?? frame.timestamp))
            let presentationTime = CMTime(
                seconds: videoPTSSeconds,
                preferredTimescale: 1_000_000_000
            )
            let appended: Bool
            if let videoInput, videoInput.isReadyForMoreMediaData,
               let pixelBufferAdaptor {
                appended = pixelBufferAdaptor.append(
                    frame.capturedImage,
                    withPresentationTime: presentationTime
                )
            } else {
                appended = false
            }

            if appended {
                statistics.videoFrameCount += 1
            } else {
                statistics.videoDroppedFrameCount += 1
            }

            let cameraMatrix = MatrixFormatting.rowMajor(frame.camera.transform)
            let intrinsics = MatrixFormatting.rowMajor(frame.camera.intrinsics)
            var row = [
                Self.decimal(frame.timestamp),
                String(currentFrameID),
                String(currentFrameID),
                Self.decimal(videoPTSSeconds),
                appended ? "true" : "false"
            ]
            row.append(contentsOf: cameraMatrix.map(Self.decimal))
            row.append(contentsOf: intrinsics.map(Self.decimal))
            row.append(String(Int(frame.camera.imageResolution.width)))
            row.append(String(Int(frame.camera.imageResolution.height)))
            row.append(MatrixFormatting.trackingState(frame.camera.trackingState))
            try arWriter.append(row)

            if !appended, assetWriter?.status == .failed {
                throw assetWriter?.error
                    ?? RoomScanRecorderError.videoAppendFailed("append 返回 false。")
            }
        } catch {
            reportFatalErrorOnce(error)
        }
    }

    private func recordFaceAnchors(_ anchors: [ARAnchor], event: String) {
        guard acceptingFrames else { return }
        let timestamp = session.currentFrame?.timestamp ?? ProcessInfo.processInfo.systemUptime
        let associatedFrameID = max(0, frameID - 1)

        for faceAnchor in anchors.compactMap({ $0 as? ARFaceAnchor }) {
            do {
                var row = [
                    Self.decimal(timestamp),
                    String(associatedFrameID),
                    faceAnchor.identifier.uuidString,
                    faceAnchor.isTracked ? "true" : "false",
                    event
                ]
                row.append(contentsOf: MatrixFormatting.rowMajor(faceAnchor.transform).map(Self.decimal))
                try faceWriter.append(row)
                statistics.faceAnchorSampleCount += 1

                if faceAnchor.isTracked != faceTrackingActive {
                    faceTrackingActive = faceAnchor.isTracked
                    eventHandler(
                        faceAnchor.isTracked ? "face_tracking_acquired" : "face_tracking_lost",
                        faceAnchor.identifier.uuidString,
                        timestamp
                    )
                }
            } catch {
                reportFatalErrorOnce(error)
            }
        }
    }

    private func reportFatalErrorOnce(_ error: Error) {
        guard !didReportFatalError else { return }
        didReportFatalError = true
        acceptingFrames = false
        errorHandler(error)
    }
}

extension RoomScanRecorder: ARSessionDelegate {
    func session(_ session: ARSession, didUpdate frame: ARFrame) {
        record(frame)
    }

    func session(_ session: ARSession, didAdd anchors: [ARAnchor]) {
        recordFaceAnchors(anchors, event: "added")
    }

    func session(_ session: ARSession, didUpdate anchors: [ARAnchor]) {
        recordFaceAnchors(anchors, event: "updated")
    }

    func session(_ session: ARSession, didRemove anchors: [ARAnchor]) {
        let removedFaces = anchors.compactMap { $0 as? ARFaceAnchor }
        guard !removedFaces.isEmpty else { return }
        let timestamp = session.currentFrame?.timestamp ?? ProcessInfo.processInfo.systemUptime
        faceTrackingActive = false
        for face in removedFaces {
            eventHandler("face_tracking_removed", face.identifier.uuidString, timestamp)
        }
    }

    func session(_ session: ARSession, didFailWithError error: Error) {
        reportFatalErrorOnce(error)
    }

    func sessionWasInterrupted(_ session: ARSession) {
        eventHandler(
            "arkit_interrupted",
            "ARSession was interrupted",
            ProcessInfo.processInfo.systemUptime
        )
    }

    func sessionInterruptionEnded(_ session: ARSession) {
        eventHandler(
            "arkit_interruption_ended",
            "ARSession interruption ended",
            ProcessInfo.processInfo.systemUptime
        )
    }
}

private extension RoomScanRecorder {
    static let matrix4Columns = (0..<4).flatMap { row in
        (0..<4).map { column in "world_T_rear_camera_\(row)\(column)" }
    }
    static let matrix3Columns = (0..<3).flatMap { row in
        (0..<3).map { column in "intrinsics_\(row)\(column)" }
    }
    static let faceMatrixColumns = (0..<4).flatMap { row in
        (0..<4).map { column in "arkit_world_T_face_anchor_\(row)\(column)" }
    }

    static let arHeader = [
        "timestamp_seconds",
        "frame_id",
        "video_frame_id",
        "video_pts_seconds",
        "video_appended"
    ] + matrix4Columns + matrix3Columns + [
        "image_width",
        "image_height",
        "tracking_state"
    ]

    static let faceHeader = [
        "timestamp_seconds",
        "frame_id",
        "anchor_id",
        "is_tracked",
        "event"
    ] + faceMatrixColumns

    static func decimal<T: BinaryFloatingPoint>(_ value: T) -> String {
        String(format: "%.9f", Double(value))
    }
}

