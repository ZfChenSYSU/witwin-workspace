import Foundation
import Network

enum UDPProbeSenderState: Equatable {
    case idle
    case resolving
    case ready
    case handshaking
    case sending
    case stopping
    case stopped
    case failed(String)
}

final class UDPProbeSender {
    typealias StateHandler = (UDPProbeSenderState) -> Void
    typealias StatisticsHandler = (UDPProbeStatistics) -> Void

    private struct PendingPacket {
        let sequence: UInt64
        let phoneMonotonicNanoseconds: UInt64
        let scheduledMonotonicNanoseconds: UInt64
    }

    private let configuration: UDPProbeConfiguration
    private let sessionID: String
    private let writer: CSVWriter
    private let queue = DispatchQueue(label: "org.witwin.recorder.udp-probe")
    private let stateHandler: StateHandler
    private let statisticsHandler: StatisticsHandler

    private var connection: NWConnection?
    private var sendTimer: DispatchSourceTimer?
    private var readinessTimeout: DispatchWorkItem?
    private var handshakeTimeout: DispatchWorkItem?
    private var forcedStopTimeout: DispatchWorkItem?
    private var sequence: UInt64 = 0
    private var pendingPackets: [UInt64: PendingPacket] = [:]
    private var statistics = UDPProbeStatistics()
    private var state: UDPProbeSenderState = .idle
    private var stopRequested = false
    private var completion: ((Result<UDPProbeStatistics, Error>) -> Void)?
    private var terminalError: Error?
    private var didFinalize = false
    private var acknowledgementReceived = false

    private var preflightSessionID: String {
        "\(sessionID).preflight"
    }

    init(
        configuration: UDPProbeConfiguration,
        sessionID: String,
        logURL: URL,
        stateHandler: @escaping StateHandler = { _ in },
        statisticsHandler: @escaping StatisticsHandler = { _ in }
    ) throws {
        self.configuration = try configuration.validated()
        self.sessionID = sessionID
        self.stateHandler = stateHandler
        self.statisticsHandler = statisticsHandler
        writer = try CSVWriter(
            url: logURL,
            header: [
                "sequence",
                "phone_monotonic_ns",
                "scheduled_monotonic_ns",
                "send_completion_monotonic_ns",
                "datagram_bytes",
                "target_host",
                "target_port",
                "send_status",
                "error"
            ]
        )
    }

    func start() throws {
        guard case .idle = state else {
            throw UDPProbeError.alreadyStarted
        }
        guard let rawPort = UInt16(exactly: configuration.port),
              let port = NWEndpoint.Port(rawValue: rawPort) else {
            throw UDPProbeError.invalidPort
        }

        updateState(.resolving)
        let parameters = NWParameters.udp
        parameters.requiredInterfaceType = .wifi
        parameters.prohibitExpensivePaths = true
        parameters.includePeerToPeer = false

        let connection = NWConnection(
            host: NWEndpoint.Host(configuration.host),
            port: port,
            using: parameters
        )
        self.connection = connection
        connection.stateUpdateHandler = { [weak self] connectionState in
            self?.queue.async {
                self?.handleConnectionState(connectionState)
            }
        }
        connection.start(queue: queue)

        let timeout = DispatchWorkItem { [weak self] in
            guard let self, !self.didFinalize else { return }
            guard self.state == .resolving else { return }
            self.fail(
                UDPProbeError.connectionFailed(
                    "8 秒内未能解析 \(self.configuration.host) 或建立 Wi-Fi UDP 路径。"
                )
            )
        }
        readinessTimeout = timeout
        queue.asyncAfter(deadline: .now() + 8, execute: timeout)
    }

    func stop(
        completion: @escaping (Result<UDPProbeStatistics, Error>) -> Void
    ) {
        queue.async { [self] in
            guard !didFinalize else {
                if let terminalError {
                    completion(.failure(terminalError))
                } else if statistics.successfulPackets == 0 {
                    completion(.failure(UDPProbeError.stoppedBeforeReady))
                } else {
                    completion(.success(statistics))
                }
                return
            }
            self.completion = completion
            stopRequested = true
            updateState(.stopping)
            sendTimer?.cancel()
            sendTimer = nil
            readinessTimeout?.cancel()
            readinessTimeout = nil
            handshakeTimeout?.cancel()
            handshakeTimeout = nil

            if pendingPackets.isEmpty {
                finalize()
                return
            }

            let timeout = DispatchWorkItem { [weak self] in
                self?.forceCompletePendingAndFinalize()
            }
            forcedStopTimeout = timeout
            queue.asyncAfter(deadline: .now() + 2, execute: timeout)
        }
    }

    private func handleConnectionState(_ connectionState: NWConnection.State) {
        guard !didFinalize else { return }
        switch connectionState {
        case .ready:
            readinessTimeout?.cancel()
            readinessTimeout = nil
            updateState(.ready)
            beginHandshake()
        case .failed(let error):
            fail(UDPProbeError.connectionFailed(error.localizedDescription))
        case .waiting:
            updateState(.resolving)
        case .cancelled:
            if stopRequested, pendingPackets.isEmpty {
                finalize()
            } else if !stopRequested {
                fail(UDPProbeError.connectionFailed("连接被系统取消。"))
            }
        case .setup, .preparing:
            break
        @unknown default:
            break
        }
    }

    private func beginHandshake() {
        guard !stopRequested, !acknowledgementReceived else { return }
        updateState(.handshaking)
        receiveAcknowledgement()
        sendHelloAttempt()

        let timeout = DispatchWorkItem { [weak self] in
            guard let self, !self.acknowledgementReceived, !self.didFinalize else {
                return
            }
            self.fail(
                UDPProbeError.connectionFailed(
                    "未收到 \(self.configuration.host):\(self.configuration.port) 的 WTWN ACK。"
                )
            )
        }
        handshakeTimeout = timeout
        queue.asyncAfter(deadline: .now() + 3, execute: timeout)
    }

    private func sendHelloAttempt() {
        guard !stopRequested,
              !acknowledgementReceived,
              statistics.handshakeAttempts < 5,
              let connection else {
            return
        }
        let attempt = UInt64(statistics.handshakeAttempts)
        let phoneNanoseconds = DispatchTime.now().uptimeNanoseconds
        statistics.handshakeAttempts += 1

        do {
            let packet = try UDPProbePacket.encode(
                sessionID: preflightSessionID,
                sequence: attempt,
                phoneMonotonicNanoseconds: phoneNanoseconds,
                datagramBytes: configuration.datagramBytes,
                flags: .hello
            )
            connection.send(
                content: packet,
                completion: .contentProcessed { [weak self] error in
                    self?.queue.async {
                        guard let self else { return }
                        if let error {
                            self.fail(
                                UDPProbeError.connectionFailed(
                                    "HELLO 发送失败：\(error.localizedDescription)"
                                )
                            )
                            return
                        }
                        if !self.acknowledgementReceived,
                           self.statistics.handshakeAttempts < 5 {
                            self.queue.asyncAfter(deadline: .now() + 0.5) {
                                self.sendHelloAttempt()
                            }
                        }
                    }
                }
            )
        } catch {
            fail(error)
        }
    }

    private func receiveAcknowledgement() {
        guard !stopRequested, !acknowledgementReceived, let connection else { return }
        connection.receiveMessage { [weak self] content, _, _, error in
            self?.queue.async {
                guard let self, !self.stopRequested, !self.didFinalize else { return }
                if let content,
                   let header = UDPProbePacket.decodeHeader(content),
                   header.flags == .acknowledgement,
                   header.sessionHash == UDPProbePacket.sessionHash(self.preflightSessionID) {
                    self.acknowledgementReceived = true
                    self.statistics.acknowledgementReceived = true
                    self.statisticsHandler(self.statistics)
                    self.handshakeTimeout?.cancel()
                    self.handshakeTimeout = nil
                    self.startSendTimer()
                    return
                }
                if error == nil {
                    self.receiveAcknowledgement()
                }
            }
        }
    }

    private func startSendTimer() {
        guard !stopRequested, sendTimer == nil else { return }
        updateState(.sending)
        let intervalSeconds = Double(configuration.datagramBytes * 8)
            / Double(configuration.bitrateBitsPerSecond)
        let intervalNanoseconds = max(
            100_000,
            Int(intervalSeconds * 1_000_000_000)
        )
        let timer = DispatchSource.makeTimerSource(queue: queue)
        timer.schedule(
            deadline: .now(),
            repeating: .nanoseconds(intervalNanoseconds),
            leeway: .microseconds(100)
        )
        timer.setEventHandler { [weak self] in
            self?.sendPacket()
        }
        sendTimer = timer
        timer.resume()
    }

    private func sendPacket() {
        guard !stopRequested, let connection else { return }
        let phoneNanoseconds = DispatchTime.now().uptimeNanoseconds
        let currentSequence = sequence
        sequence &+= 1
        let pending = PendingPacket(
            sequence: currentSequence,
            phoneMonotonicNanoseconds: phoneNanoseconds,
            scheduledMonotonicNanoseconds: phoneNanoseconds
        )

        do {
            let packet = try UDPProbePacket.encode(
                sessionID: sessionID,
                sequence: currentSequence,
                phoneMonotonicNanoseconds: phoneNanoseconds,
                datagramBytes: configuration.datagramBytes
            )
            pendingPackets[currentSequence] = pending
            statistics.attemptedPackets += 1
            statistics.firstPhoneMonotonicNanoseconds =
                statistics.firstPhoneMonotonicNanoseconds ?? phoneNanoseconds
            statistics.lastPhoneMonotonicNanoseconds = phoneNanoseconds

            connection.send(
                content: packet,
                completion: .contentProcessed { [weak self] error in
                    self?.queue.async {
                        self?.completePacket(
                            sequence: currentSequence,
                            error: error
                        )
                    }
                }
            )
        } catch {
            terminalError = error
            fail(error)
        }
    }

    private func completePacket(sequence: UInt64, error: NWError?) {
        guard let pending = pendingPackets.removeValue(forKey: sequence) else {
            return
        }
        let completionNanoseconds = DispatchTime.now().uptimeNanoseconds
        if let error {
            statistics.failedPackets += 1
            appendLog(
                pending,
                completionNanoseconds: completionNanoseconds,
                status: "failed",
                error: error.localizedDescription
            )
        } else {
            statistics.successfulPackets += 1
            statistics.successfulBytes += configuration.datagramBytes
            appendLog(
                pending,
                completionNanoseconds: completionNanoseconds,
                status: "accepted_by_local_udp_stack",
                error: ""
            )
        }

        let completedPackets = statistics.successfulPackets + statistics.failedPackets
        if completedPackets % 25 == 0 {
            statisticsHandler(statistics)
        }
        if stopRequested, pendingPackets.isEmpty {
            finalize()
        }
    }

    private func appendLog(
        _ packet: PendingPacket,
        completionNanoseconds: UInt64,
        status: String,
        error: String
    ) {
        do {
            try writer.append([
                String(packet.sequence),
                String(packet.phoneMonotonicNanoseconds),
                String(packet.scheduledMonotonicNanoseconds),
                String(completionNanoseconds),
                String(configuration.datagramBytes),
                configuration.host,
                String(configuration.port),
                status,
                error
            ])
        } catch {
            terminalError = error
        }
    }

    private func fail(_ error: Error) {
        guard !didFinalize else { return }
        terminalError = error
        updateState(.failed(error.localizedDescription))
        stopRequested = true
        sendTimer?.cancel()
        sendTimer = nil
        readinessTimeout?.cancel()
        readinessTimeout = nil
        handshakeTimeout?.cancel()
        handshakeTimeout = nil
        connection?.cancel()
        if pendingPackets.isEmpty {
            finalize()
        }
    }

    private func forceCompletePendingAndFinalize() {
        guard !didFinalize else { return }
        let completionNanoseconds = DispatchTime.now().uptimeNanoseconds
        for packet in pendingPackets.values.sorted(by: { $0.sequence < $1.sequence }) {
            statistics.failedPackets += 1
            appendLog(
                packet,
                completionNanoseconds: completionNanoseconds,
                status: "cancelled_before_completion",
                error: "stop timeout"
            )
        }
        pendingPackets.removeAll()
        finalize()
    }

    private func finalize() {
        guard !didFinalize else { return }
        didFinalize = true
        forcedStopTimeout?.cancel()
        forcedStopTimeout = nil
        connection?.stateUpdateHandler = nil
        connection?.cancel()
        connection = nil
        do {
            try writer.close()
        } catch {
            terminalError = terminalError ?? error
        }
        statisticsHandler(statistics)

        if let terminalError {
            updateState(.failed(terminalError.localizedDescription))
            completion?(.failure(terminalError))
        } else if statistics.successfulPackets == 0 {
            let error = UDPProbeError.stoppedBeforeReady
            updateState(.failed(error.localizedDescription))
            completion?(.failure(error))
        } else {
            updateState(.stopped)
            completion?(.success(statistics))
        }
        completion = nil
    }

    private func updateState(_ newState: UDPProbeSenderState) {
        state = newState
        stateHandler(newState)
    }
}
