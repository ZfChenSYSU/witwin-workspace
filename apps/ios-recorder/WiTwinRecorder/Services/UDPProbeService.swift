import Foundation

@MainActor
final class UDPProbeService: ObservableObject {
    @Published private(set) var state: UDPProbeSenderState = .idle
    @Published private(set) var statusMessage = "尚未运行 UDP 上行测试"
    @Published private(set) var statistics = UDPProbeStatistics()
    @Published private(set) var logFileURL: URL?
    @Published private(set) var sessionID: String?

    private var sender: UDPProbeSender?
    private var automaticStopTask: Task<Void, Never>?
    private var requestedDurationSeconds = 10

    var isRunning: Bool {
        switch state {
        case .resolving, .ready, .handshaking, .sending, .stopping:
            return true
        case .idle, .stopped, .failed:
            return false
        }
    }

    func start(
        configuration: UDPProbeConfiguration,
        durationSeconds: Int
    ) {
        guard !isRunning else { return }
        do {
            let validated = try configuration.validated()
            guard (1...600).contains(durationSeconds) else {
                throw UDPProbeError.invalidConfiguration("测试时长必须在 1…600 秒之间。")
            }

            let documents = try FileManager.default.url(
                for: .documentDirectory,
                in: .userDomainMask,
                appropriateFor: nil,
                create: true
            )
            let root = documents.appendingPathComponent("UDPTests", isDirectory: true)
            try FileManager.default.createDirectory(
                at: root,
                withIntermediateDirectories: true
            )
            let identity = "udp_test_\(Int(Date().timeIntervalSince1970))"
            let directory = root.appendingPathComponent(identity, isDirectory: true)
            try FileManager.default.createDirectory(
                at: directory,
                withIntermediateDirectories: false
            )
            let logURL = directory.appendingPathComponent("udp_tx.csv")

            let sender = try UDPProbeSender(
                configuration: validated,
                sessionID: identity,
                logURL: logURL,
                stateHandler: { [weak self] state in
                    Task { @MainActor in
                        self?.handle(state)
                    }
                },
                statisticsHandler: { [weak self] statistics in
                    Task { @MainActor in
                        self?.statistics = statistics
                    }
                }
            )
            self.sender = sender
            requestedDurationSeconds = durationSeconds
            sessionID = identity
            logFileURL = logURL
            statistics = UDPProbeStatistics()
            state = .resolving
            statusMessage = "正在解析 \(validated.host) 并建立 Wi-Fi UDP 路径…"
            try sender.start()
        } catch {
            state = .failed(error.localizedDescription)
            statusMessage = error.localizedDescription
            sender = nil
        }
    }

    func stop() {
        guard isRunning, let sender else { return }
        automaticStopTask?.cancel()
        automaticStopTask = nil
        state = .stopping
        statusMessage = "正在停止 UDP 发包并关闭日志…"
        sender.stop { [weak self] result in
            Task { @MainActor in
                guard let self else { return }
                switch result {
                case .success(let statistics):
                    self.statistics = statistics
                    self.state = .stopped
                    self.statusMessage = String(
                        format: "完成：%d 包，%.3f Mbit/s（仅表示本地发送成功）",
                        statistics.successfulPackets,
                        statistics.achievedBitrateBitsPerSecond / 1_000_000
                    )
                case .failure(let error):
                    self.state = .failed(error.localizedDescription)
                    self.statusMessage = error.localizedDescription
                }
                self.sender = nil
            }
        }
    }

    func handleAppBecameInactive() {
        if isRunning {
            stop()
        }
    }

    private func handle(_ newState: UDPProbeSenderState) {
        state = newState
        switch newState {
        case .idle:
            statusMessage = "尚未运行 UDP 上行测试"
        case .resolving:
            statusMessage = "等待名称解析和 Wi-Fi 路径…"
        case .ready:
            statusMessage = "UDP 路径就绪"
        case .handshaking:
            statusMessage = "正在等待 Linux WTWN 接收器 ACK…"
        case .sending:
            statusMessage = "正在发送 WTWN UDP 上行探测包…"
            scheduleAutomaticStop()
        case .stopping:
            statusMessage = "正在停止 UDP 发包…"
        case .stopped:
            break
        case .failed(let detail):
            statusMessage = detail
            automaticStopTask?.cancel()
            automaticStopTask = nil
            sender = nil
        }
    }

    private func scheduleAutomaticStop() {
        guard automaticStopTask == nil else { return }
        automaticStopTask = Task { @MainActor [weak self] in
            guard let self else { return }
            try? await Task.sleep(
                nanoseconds: UInt64(requestedDurationSeconds) * 1_000_000_000
            )
            guard !Task.isCancelled else { return }
            stop()
        }
    }
}
