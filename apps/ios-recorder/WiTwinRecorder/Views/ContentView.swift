import SwiftUI

struct ContentView: View {
    @Environment(\.scenePhase) private var scenePhase
    @StateObject private var probe = CapabilityProbeService()
    @StateObject private var faceDistance = FaceDistanceService()
    @StateObject private var recorder = SessionRecorder()
    @StateObject private var udpProbe = UDPProbeService()
    @State private var phoneAssemblyID = "phone-rig-001"
    @State private var udpHost = UDPProbeConfiguration.defaultHost
    @State private var udpPort = UDPProbeConfiguration.defaultPort
    @State private var udpBitrate = UDPProbeConfiguration.defaultBitrateBitsPerSecond
    @State private var udpDatagramBytes = UDPProbeConfiguration.defaultDatagramBytes
    @State private var udpDurationSeconds = 10
    @State private var includeUDPInRecorder = false

    var body: some View {
        NavigationStack {
            List {
                faceDistanceSection
                p2UDPProbeSection
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
                    faceDistance.stop()
                    recorder.handleAppBecameInactive()
                    udpProbe.handleAppBecameInactive()
                } else {
                    faceDistance.start()
                }
            }
            .onAppear {
                faceDistance.start()
            }
        }
    }

    @ViewBuilder
    private var faceDistanceSection: some View {
        Section("实时人脸测距（调试）") {
            Label(faceDistance.statusMessage, systemImage: faceDistance.isRunning ? "dot.radiowaves.left.and.right" : "circle.dashed")
                .foregroundStyle(faceDistance.isRunning ? .blue : .secondary)

            if let distance = faceDistance.distanceMeters {
                valueRow("人脸中心—后置相机", String(format: "%.3f m（%.1f cm）", distance, distance * 100))
                if let position = faceDistance.relativePositionMeters {
                    valueRow(
                        "相对坐标 x/y/z",
                        String(format: "%.3f / %.3f / %.3f m", position.x, position.y, position.z)
                    )
                }
                Text("这是 ARKit 世界坐标中人脸锚点中心到后置相机参考点的近似距离。前摄像头—机身外参和人脸—胸腔标定尚未完成，不能直接当作胸腔真值。")
                    .font(.footnote)
                    .foregroundStyle(.orange)
            } else {
                Text("尚未取得有效人脸距离；请保持整张脸可见、光线充足并等待跟踪状态变为 normal。")
                    .foregroundStyle(.secondary)
            }

            Button(faceDistance.isRunning ? "重新测距" : "开始测距") {
                faceDistance.stop()
                faceDistance.start()
            }
        }
    }

    @ViewBuilder
    private var p2UDPProbeSection: some View {
        Section("P2 UDP 上行独立测试") {
            Label(udpProbe.statusMessage, systemImage: udpStatusSymbol)
                .foregroundStyle(udpStatusColor)

            TextField("目标 IP 或主机名", text: $udpHost)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .disabled(udpProbe.isRunning)

            TextField("UDP 端口", value: $udpPort, format: .number)
                .keyboardType(.numberPad)
                .disabled(udpProbe.isRunning)
            Stepper(
                "码率：\(Double(udpBitrate) / 1_000_000, specifier: "%.1f") Mbit/s",
                value: $udpBitrate,
                in: 100_000...10_000_000,
                step: 100_000
            )
            .disabled(udpProbe.isRunning)
            Stepper(
                "数据报：\(udpDatagramBytes) B",
                value: $udpDatagramBytes,
                in: 32...1_400,
                step: 8
            )
            .disabled(udpProbe.isRunning)
            Stepper(
                "时长：\(udpDurationSeconds) s",
                value: $udpDurationSeconds,
                in: 1...600
            )
            .disabled(udpProbe.isRunning)

            HStack {
                Button {
                    udpProbe.start(
                        configuration: UDPProbeConfiguration(
                            host: udpHost,
                            port: udpPort,
                            bitrateBitsPerSecond: udpBitrate,
                            datagramBytes: udpDatagramBytes
                        ),
                        durationSeconds: udpDurationSeconds
                    )
                } label: {
                    Label("开始发包", systemImage: "antenna.radiowaves.left.and.right")
                }
                .disabled(udpProbe.isRunning || recorder.isBusy)

                Button(role: .destructive) {
                    udpProbe.stop()
                } label: {
                    Label("停止", systemImage: "stop.circle")
                }
                .disabled(!udpProbe.isRunning)
            }

            if udpProbe.statistics.attemptedPackets > 0 {
                valueRow("HELLO 次数", "\(udpProbe.statistics.handshakeAttempts)")
                boolRow("已收到 ACK", udpProbe.statistics.acknowledgementReceived)
                valueRow("尝试包数", "\(udpProbe.statistics.attemptedPackets)")
                valueRow("本地发送成功", "\(udpProbe.statistics.successfulPackets)")
                valueRow("本地发送失败", "\(udpProbe.statistics.failedPackets)")
                valueRow(
                    "实际码率",
                    String(
                        format: "%.3f Mbit/s",
                        udpProbe.statistics.achievedBitrateBitsPerSecond / 1_000_000
                    )
                )
            } else if udpProbe.statistics.handshakeAttempts > 0 {
                valueRow("HELLO 次数", "\(udpProbe.statistics.handshakeAttempts)")
                boolRow("已收到 ACK", udpProbe.statistics.acknowledgementReceived)
            }

            if let url = udpProbe.logFileURL {
                ShareLink(item: url) {
                    Label("导出 udp_tx.csv", systemImage: "square.and.arrow.up")
                }
            }

            Text("首次默认使用 192.168.3.31:5201。开始持续发包前必须收到 Linux WTWN 接收器的 ACK；iPerf3 UDP 与 WTWN UDP 不能同时占用同一个端口。")
                .font(.footnote)
                .foregroundStyle(.secondary)
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

            Toggle("同时发送 P2 UDP 上行", isOn: $includeUDPInRecorder)
                .disabled(recorder.isBusy || udpProbe.isRunning)
            if includeUDPInRecorder {
                Text("使用上方配置：\(udpHost):\(udpPort)，\(udpDatagramBytes) B，\(Double(udpBitrate) / 1_000_000, specifier: "%.1f") Mbit/s")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }

            if recorder.state == .recording || recorder.state == .stopping {
                LabeledContent("已采集", value: duration(recorder.elapsedSeconds))
                    .monospacedDigit()
            }

            HStack {
                Button {
                    recorder.start(
                        phoneAssemblyID: phoneAssemblyID,
                        udpConfiguration: includeUDPInRecorder
                            ? UDPProbeConfiguration(
                                host: udpHost,
                                port: udpPort,
                                bitrateBitsPerSecond: udpBitrate,
                                datagramBytes: udpDatagramBytes
                            )
                            : nil
                    )
                } label: {
                    Label("开始", systemImage: "record.circle")
                }
                .disabled(!recorder.canStart || probe.isRunning || udpProbe.isRunning)

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

            Text("代表性房间扫描建议 1–5 分钟，以覆盖完整、视角重叠和闭环完成为停止条件。采集期间请保持 App 在前台。")
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

    private var udpStatusSymbol: String {
        switch udpProbe.state {
        case .idle: return "circle.dashed"
        case .resolving: return "network"
        case .ready, .handshaking, .sending: return "antenna.radiowaves.left.and.right"
        case .stopping: return "stopwatch"
        case .stopped: return "checkmark.circle.fill"
        case .failed: return "xmark.octagon.fill"
        }
    }

    private var udpStatusColor: Color {
        switch udpProbe.state {
        case .idle: return .secondary
        case .resolving, .ready, .handshaking, .stopping: return .blue
        case .sending: return .green
        case .stopped: return .green
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
