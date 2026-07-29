import ARKit
import Foundation
import simd

enum MatrixFormatting {
    static func rowMajor(_ matrix: simd_float4x4) -> [Float] {
        (0..<4).flatMap { row in
            (0..<4).map { column in
                matrix[column][row]
            }
        }
    }

    static func rowMajor(_ matrix: simd_float3x3) -> [Float] {
        (0..<3).flatMap { row in
            (0..<3).map { column in
                matrix[column][row]
            }
        }
    }

    static func trackingState(_ state: ARCamera.TrackingState) -> String {
        switch state {
        case .normal:
            return "normal"
        case .notAvailable:
            return "not_available"
        case .limited(let reason):
            return "limited:\(trackingReason(reason))"
        }
    }

    private static func trackingReason(_ reason: ARCamera.TrackingState.Reason) -> String {
        switch reason {
        case .initializing:
            return "initializing"
        case .excessiveMotion:
            return "excessive_motion"
        case .insufficientFeatures:
            return "insufficient_features"
        case .relocalizing:
            return "relocalizing"
        @unknown default:
            return "unknown"
        }
    }
}

