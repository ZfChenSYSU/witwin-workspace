import SwiftUI

struct ContentView: View {
    @StateObject private var probe = CapabilityProbeService()

    var body: some View {
        NavigationStack {
            List {
                Section("P0 能力探针") {
                    Label(probe.statusMessage, systemImage: statusSymbol)
                        .foregroundStyle(statusColor)

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
        }
    }

    private var statusSymbol: String {
        if probe.isRunning { return "hourglass" }
        if probe.report != nil { return "checkmark.circle" }
        return "circle.dashed"
    }

    private var statusColor: Color {
        if probe.isRunning { return .blue }
        if probe.report != nil { return .green }
        return .secondary
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
