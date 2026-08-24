// swift-tools-version: 6.2
import PackageDescription

let package = Package(
    name: "ElasticUMANative",
    platforms: [.macOS(.v13)],
    products: [
        .executable(
            name: "elasticuma-pressure-monitor",
            targets: ["ElasticUMAPressureMonitor"]
        )
    ],
    targets: [
        .executableTarget(
            name: "ElasticUMAPressureMonitor",
            path: "Sources/ElasticUMAPressureMonitor"
        )
    ]
)
