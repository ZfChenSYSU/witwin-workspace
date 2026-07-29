import SwiftUI

struct ContentView: View {
    @Environment(\.scenePhase) private var scenePhase
    @StateObject private var probe = CapabilityProbeService()
    @StateObject private var recorder = SessionRecorder()
    @State private var phoneAssemblyID = "phone-rig-001"

    var body: some View {
        NavigationStack {
            List {
                p1RecordingSection
                p1ResultSection

                Section("P0 能力探针") {
                    Label(probe.statusMessage, systemImage: probeStatusSymbol)
                        .foregroundStyle(probeStatusColor)

                    Button {
                        probe.run()
                    } label: {
                        Label("运行并保存能力探针", systemImage: "waveform.path.ecg")
                    }
                    .disabled(probe.isRunning)

                    if probe.isRunning {
                        ProgressView()
                    }

                    if let url = probe.reportFileURL {
                        ShareLink(item: url) {
                            Label("导出 capabilities.json", systemImage: "square.and.arrow.up")
                        }
                    }
                }

                if let report = probe.report {
                    environmentSection(report)
                    arkitSection(report)
                    cameraSection(report)
                    motionAndSystemSection(report)
                    validationSection(report)
                } else {
                    Section("说明") {
                        Text("探针会记录设备、iOS、ARKit、相机、CoreMotion、存储和热状态，并将结果写入 App 的 Documents/capabilities.json。")
                        Text("模拟器结果只用于验证程序可运行；科研 Go/No-Go 必须以 iPhone 11 Pro 真机输出为准。")
                            .foregroundStyle(.orange)
                    }
                }
            }
            .navigationTitle("WiTwin Recorder")
            .onChange(of: scenePhase) { phase in
                if phase != .active {
                    recorder.handleAppBecameInactive()
                }
            }
        }
    }

    @ViewBuilder
    private var p1RecordingSection: some View {
        Section("P1 同步采集") {
            Label(recorder.statusMessage, systemImage: recorderStatusSymbol)
                .foregroundStyle(recorderStatusColor)

            TextField("手机—夹具—稳定器装配编号", text: $phoneAssemblyID)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .disabled(recorder.isBusy)

            if recorder.state == .recording || recorder.state == .stopping {
                LabeledContent("已采集", value: duration(recorder.elapsedSeconds))
                    .monospacedDigit()
            }

            HStack {
                Button {
                    recorder.start(phoneAssemblyID: phoneAssemblyID)
                } label: {
                    Label("开始", systemImage: "record.circle")
                }
                .disabled(!recorder.canStart || probe.isRunning)

                Button {
                    recorder.markEvent()
                } label: {
                    Label("标记", systemImage: "flag")
                }
                .disabled(recorder.state != .recording)

                Button(role: .destructive) {
                    recorder.stop()
                } label: {
                    Label("停止", systemImage: "stop.circle")
                }
                .disabled(!recorder.canStop)
            }

            Text("首轮请连续采集 1 分钟；通过自动检查后再做 10 分钟稳定性测试。采集期间请保持 App 在前台。")
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
    }

    @ViewBuilder
    private var p1ResultSection: some View {
        if let report = recorder.validationReport {
            Section("P1 自动检查") {
                boolRow("通过", report.passed)
                valueRow("时长", duration(report.statistics.durationSeconds))
                valueRow("ARFrame", "\(report.statistics.arFrameCount)")
                valueRow("视频帧", "\(report.statistics.videoFrameCount)")
                valueRow(
                    "映射缺失率",
                    String(format: "%.3f%%", report.statistics.videoMappingMissingRate * 100)
                )
                valueRow("IMU 样本", "\(report.statistics.imuSampleCount)")
                valueRow("人脸锚点", "\(report.statistics.faceAnchorSampleCount)")

                ForEach(report.errors, id: \.self) { error in
                    Label(error, systemImage: "xmark.octagon")
                        .foregroundStyle(.red)
                }
                ForEach(report.warnings, id: \.self) { warning in
                    Label(warning, systemImage: "exclamationmark.triangle")
                        .foregroundStyle(.orange)
                }
            }
        }

        if let url = recorder.lastSessionURL {
            Section("导出") {
                ShareLink(item: url) {
                    Label("导出完整 session 文件夹", systemImage: "square.and.arrow.up")
                }
                Text(url.lastPathComponent)
                    .font(.footnote.monospaced())
                    .textSelection(.enabled)
            }
        }
    }

    private var probeStatusSymbol: String {
        if probe.isRunning { return "hourglass" }
        if probe.report != nil { return "checkmark.circle" }
        return "circle.dashed"
    }

    private var probeStatusColor: Color {
        if probe.isRunning { return .blue }
        if probe.report != nil { return .green }
        return .secondary
    }

    private var recorderStatusSymbol: String {
        switch recorder.state {
        case .idle: return "circle.dashed"
        case .preparing: return "hourglass"
        case .recording: return "record.circle.fill"
        case .stopping: return "stopwatch"
        case .completed: return "checkmark.circle.fill"
        case .failed: return "xmark.octagon.fill"
        }
    }

    private var recorderStatusColor: Color {
        switch recorder.state {
        case .idle: return .secondary
        case .preparing, .stopping: return .blue
        case .recording: return .red
        case .completed: return .green
        case .failed: return .red
        }
    }

    private func duration(_ seconds: TimeInterval) -> String {
        let total = max(0, Int(seconds.rounded()))
        return String(format: "%02d:%02d", total / 60, total % 60)
    }

    @ViewBuilder
    private func environmentSection(_ report: CapabilityReport) -> some View {
        Section("设备与环境") {
            valueRow("型号", report.device.modelName)
            valueRow("硬件标识", report.device.modelIdentifier)
            valueRow("系统", "\(report.device.systemName) \(report.device.systemVersion)")
            valueRow("App", "\(report.app.version) (\(report.app.build))")
            valueRow("运行环境", report.executionEnvironment.isSimulator ? "Simulator" : "Physical device")
        }
    }

    @ViewBuilder
    private func arkitSection(_ report: CapabilityReport) -> some View {
        Section("ARKit 静态能力") {
            boolRow("世界跟踪", report.arkit.worldTrackingSupported)
            boolRow("世界跟踪 + 用户人脸", report.arkit.worldTrackingSupportsUserFaceTracking)
            boolRow("独立人脸跟踪", report.arkit.faceTrackingSupported)
        }
    }

    @ViewBuilder
    private func cameraSection(_ report: CapabilityReport) -> some View {
        Section("相机") {
            valueRow("授权", report.camera.authorizationStatus)
            valueRow("发现设备数", "\(report.camera.availableDevices.count)")
            if let width = report.camera.capturedImageWidth,
               let height = report.camera.capturedImageHeight {
                valueRow("采集帧", "\(width) × \(height)")
            }
            if let width = report.camera.imageResolutionWidth,
               let height = report.camera.imageResolutionHeight {
                valueRow("ARCamera 分辨率", "\(width) × \(height)")
            }
        }
    }

    @ViewBuilder
    private func motionAndSystemSection(_ report: CapabilityReport) -> some View {
        Section("运动、存储与热状态") {
            valueRow("Motion 授权", report.motion.authorizationStatus)
            boolRow("加速度计", report.motion.accelerometerAvailable)
            boolRow("陀螺仪", report.motion.gyroAvailable)
            boolRow("Device Motion", report.motion.deviceMotionAvailable)
            boolRow("磁力计", report.motion.magnetometerAvailable)
            valueRow("热状态", report.thermalState)
            if let bytes = report.storage.volumeAvailableCapacityForImportantUsageBytes {
                valueRow("可用空间", ByteCountFormatter.string(fromByteCount: bytes, countStyle: .file))
            }
        }
    }

    @ViewBuilder
    private func validationSection(_ report: CapabilityReport) -> some View {
        Section("运行时验证") {
            valueRow("状态", report.runtimeValidation.status)
            boolRow("收到 ARFrame", report.runtimeValidation.arFrameReceived)
            boolRow("已启用用户人脸跟踪", report.runtimeValidation.userFaceTrackingEnabled)
            boolRow("观察到 ARFaceAnchor", report.runtimeValidation.faceAnchorObserved)
            if let timestamp = report.runtimeValidation.arFrameTimestampSeconds {
                valueRow("ARFrame 时间戳", String(format: "%.6f s", timestamp))
            }
            if let timestamp = report.runtimeValidation.faceAnchorFrameTimestampSeconds {
                valueRow("人脸锚点帧时间戳", String(format: "%.6f s", timestamp))
            }
            if let tracking = report.runtimeValidation.trackingState {
                valueRow("跟踪状态", tracking)
            }
            ForEach(report.runtimeValidation.notes, id: \.self) { note in
                Text(note)
                    .foregroundStyle(.orange)
            }
        }
    }

    @ViewBuilder
    private func valueRow(_ title: String, _ value: String) -> some View {
        LabeledContent(title, value: value)
    }

    @ViewBuilder
    private func boolRow(_ title: String, _ value: Bool) -> some View {
        LabeledContent(title) {
            Image(systemName: value ? "checkmark.circle.fill" : "xmark.circle.fill")
                .foregroundStyle(value ? .green : .red)
                .accessibilityLabel(value ? "支持" : "不支持")
        }
    }
}
