import CryptoKit
import Foundation

struct UDPProbeConfiguration: Codable, Equatable {
    static let defaultHost = "192.168.3.31"
    static let defaultPort = 5201
    static let defaultBitrateBitsPerSecond = 2_000_000
    static let defaultDatagramBytes = 1_200

    let host: String
    let port: Int
    let bitrateBitsPerSecond: Int
    let datagramBytes: Int

    static let experimentalDefault = UDPProbeConfiguration(
        host: defaultHost,
        port: defaultPort,
        bitrateBitsPerSecond: defaultBitrateBitsPerSecond,
        datagramBytes: defaultDatagramBytes
    )

    func validated() throws -> UDPProbeConfiguration {
        let trimmedHost = host.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedHost.isEmpty else {
            throw UDPProbeError.invalidConfiguration("目标主机名不能为空。")
        }
        guard (1...65_535).contains(port) else {
            throw UDPProbeError.invalidConfiguration("目标端口必须在 1…65535 之间。")
        }
        guard bitrateBitsPerSecond > 0 else {
            throw UDPProbeError.invalidConfiguration("目标码率必须大于 0。")
        }
        guard datagramBytes >= UDPProbePacket.headerLength, datagramBytes <= 1_400 else {
            throw UDPProbeError.invalidConfiguration(
                "UDP 数据报长度必须在 \(UDPProbePacket.headerLength)…1400 字节之间。"
            )
        }
        return UDPProbeConfiguration(
            host: trimmedHost,
            port: port,
            bitrateBitsPerSecond: bitrateBitsPerSecond,
            datagramBytes: datagramBytes
        )
    }

    var packetsPerSecond: Double {
        Double(bitrateBitsPerSecond) / Double(datagramBytes * 8)
    }
}

enum UDPProbeError: LocalizedError {
    case invalidConfiguration(String)
    case invalidPort
    case alreadyStarted
    case connectionFailed(String)
    case stoppedBeforeReady

    var errorDescription: String? {
        switch self {
        case .invalidConfiguration(let detail):
            return detail
        case .invalidPort:
            return "UDP 端口不能转换为 Network.framework 端口。"
        case .alreadyStarted:
            return "UDP 发送器已经启动。"
        case .connectionFailed(let detail):
            return "UDP 连接失败：\(detail)"
        case .stoppedBeforeReady:
            return "UDP 发送器在目标主机解析或连接就绪前停止。"
        }
    }
}

enum UDPProbePacket {
    enum Flags: UInt8 {
        case data = 0
        case hello = 1
        case acknowledgement = 2
    }

    struct Header: Equatable {
        let flags: Flags
        let sessionHash: UInt64
        let sequence: UInt64
        let phoneMonotonicNanoseconds: UInt64
    }

    static let magic = Data("WTWN".utf8)
    static let protocolVersion: UInt8 = 1
    static let headerLength = 32

    static func encode(
        sessionID: String,
        sequence: UInt64,
        phoneMonotonicNanoseconds: UInt64,
        datagramBytes: Int,
        flags: Flags = .data
    ) throws -> Data {
        guard datagramBytes >= headerLength else {
            throw UDPProbeError.invalidConfiguration(
                "数据报小于 \(headerLength) 字节固定头。"
            )
        }

        var packet = Data()
        packet.reserveCapacity(datagramBytes)
        packet.append(magic)
        packet.append(protocolVersion)
        packet.append(flags.rawValue)
        packet.appendBigEndian(UInt16(headerLength))

        let digest = SHA256.hash(data: Data(sessionID.utf8))
        packet.append(contentsOf: digest.prefix(8))
        packet.appendBigEndian(sequence)
        packet.appendBigEndian(phoneMonotonicNanoseconds)

        let fillerCount = datagramBytes - headerLength
        if fillerCount > 0 {
            packet.append(
                Data(
                    repeating: UInt8(truncatingIfNeeded: sequence),
                    count: fillerCount
                )
            )
        }
        return packet
    }

    static func decodeHeader(_ packet: Data) -> Header? {
        guard packet.count >= headerLength,
              Data(packet[0..<4]) == magic,
              packet[4] == protocolVersion,
              let flags = Flags(rawValue: packet[5]),
              packet.readBigEndianUInt16(at: 6) == UInt16(headerLength),
              let sessionHash = packet.readBigEndianUInt64(at: 8),
              let sequence = packet.readBigEndianUInt64(at: 16),
              let phoneNanoseconds = packet.readBigEndianUInt64(at: 24) else {
            return nil
        }
        return Header(
            flags: flags,
            sessionHash: sessionHash,
            sequence: sequence,
            phoneMonotonicNanoseconds: phoneNanoseconds
        )
    }

    static func sessionHash(_ sessionID: String) -> UInt64 {
        SHA256.hash(data: Data(sessionID.utf8))
            .prefix(8)
            .reduce(UInt64(0)) { partial, byte in
                (partial << 8) | UInt64(byte)
            }
    }

    static func sessionHashHex(_ sessionID: String) -> String {
        String(format: "%016llx", sessionHash(sessionID))
    }
}

struct UDPProbeStatistics: Equatable {
    var attemptedPackets = 0
    var successfulPackets = 0
    var failedPackets = 0
    var successfulBytes = 0
    var firstPhoneMonotonicNanoseconds: UInt64?
    var lastPhoneMonotonicNanoseconds: UInt64?
    var handshakeAttempts = 0
    var acknowledgementReceived = false

    var durationSeconds: Double {
        guard let firstPhoneMonotonicNanoseconds,
              let lastPhoneMonotonicNanoseconds,
              lastPhoneMonotonicNanoseconds >= firstPhoneMonotonicNanoseconds else {
            return 0
        }
        return Double(lastPhoneMonotonicNanoseconds - firstPhoneMonotonicNanoseconds)
            / 1_000_000_000
    }

    var achievedBitrateBitsPerSecond: Double {
        guard durationSeconds > 0 else { return 0 }
        return Double(successfulBytes * 8) / durationSeconds
    }
}

private extension Data {
    mutating func appendBigEndian<T: FixedWidthInteger>(_ value: T) {
        var bigEndian = value.bigEndian
        Swift.withUnsafeBytes(of: &bigEndian) { bytes in
            append(contentsOf: bytes)
        }
    }

    func readBigEndianUInt16(at offset: Int) -> UInt16? {
        guard count >= offset + 2 else { return nil }
        return self[offset..<(offset + 2)].reduce(UInt16(0)) { partial, byte in
            (partial << 8) | UInt16(byte)
        }
    }

    func readBigEndianUInt64(at offset: Int) -> UInt64? {
        guard count >= offset + 8 else { return nil }
        return self[offset..<(offset + 8)].reduce(UInt64(0)) { partial, byte in
            (partial << 8) | UInt64(byte)
        }
    }
}
