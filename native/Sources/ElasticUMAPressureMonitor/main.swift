import Dispatch
import Foundation

private let output = FileHandle.standardOutput
private let queue = DispatchQueue(label: "org.elasticuma.pressure-monitor")
private let encoder = JSONEncoder()

private struct Event: Codable {
    let schemaVersion: Int
    let kind: String
    let level: String?
    let rawMask: UInt
    let capturedAt: String
    let monotonicNanoseconds: UInt64
    let pid: Int32
}

private func timestamp() -> String {
    ISO8601DateFormatter().string(from: Date())
}

private func write(kind: String, level: String? = nil, rawMask: UInt = 0) {
    let event = Event(
        schemaVersion: 1,
        kind: kind,
        level: level,
        rawMask: rawMask,
        capturedAt: timestamp(),
        monotonicNanoseconds: DispatchTime.now().uptimeNanoseconds,
        pid: ProcessInfo.processInfo.processIdentifier
    )
    do {
        var data = try encoder.encode(event)
        data.append(0x0A)
        try output.write(contentsOf: data)
    } catch {
        FileHandle.standardError.write(Data("pressure monitor write failed\n".utf8))
        exit(2)
    }
}

private func level(for data: DispatchSource.MemoryPressureEvent) -> String {
    if data.contains(.critical) { return "critical" }
    if data.contains(.warning) { return "warning" }
    if data.contains(.normal) { return "normal" }
    return "unknown"
}

let pressure = DispatchSource.makeMemoryPressureSource(
    eventMask: [.normal, .warning, .critical],
    queue: queue
)
pressure.setEventHandler {
    let data = pressure.data
    write(kind: "pressure", level: level(for: data), rawMask: data.rawValue)
}

write(kind: "start")
pressure.resume()
dispatchMain()
