import Foundation

enum CSVWriterError: LocalizedError {
    case alreadyClosed

    var errorDescription: String? {
        switch self {
        case .alreadyClosed:
            return "CSV 文件已经关闭。"
        }
    }
}

final class CSVWriter {
    private let lock = NSLock()
    private var fileHandle: FileHandle?
    private(set) var rowCount = 0

    init(url: URL, header: [String]) throws {
        FileManager.default.createFile(atPath: url.path, contents: nil)
        fileHandle = try FileHandle(forWritingTo: url)
        try appendUnlocked(header)
    }

    func append(_ fields: [String]) throws {
        lock.lock()
        defer { lock.unlock() }
        guard fileHandle != nil else {
            throw CSVWriterError.alreadyClosed
        }
        try appendUnlocked(fields)
        rowCount += 1
    }

    func close() throws {
        lock.lock()
        defer { lock.unlock() }
        guard let fileHandle else { return }
        try fileHandle.synchronize()
        try fileHandle.close()
        self.fileHandle = nil
    }

    private func appendUnlocked(_ fields: [String]) throws {
        let line = fields.map(Self.escape).joined(separator: ",") + "\n"
        try fileHandle?.write(contentsOf: Data(line.utf8))
    }

    private static func escape(_ value: String) -> String {
        guard value.contains(",") || value.contains("\"") || value.contains("\n") else {
            return value
        }
        return "\"\(value.replacingOccurrences(of: "\"", with: "\"\""))\""
    }
}
