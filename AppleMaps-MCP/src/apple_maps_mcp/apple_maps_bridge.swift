import Foundation
import MapKit

struct BridgeFailure: Error {
    let errorCode: String
    let message: String
    let suggestion: String?
}

struct ErrorPayload: Encodable {
    let ok = false
    let error_code: String
    let message: String
    let suggestion: String?
}

struct PlaceRecord: Encodable {
    let name: String
    let address: String?
    let latitude: Double?
    let longitude: Double?
    let phone: String?
    let url: String?
}

struct PlaceListPayload: Encodable {
    let places: [PlaceRecord]
}

struct DirectionsPayload: Encodable {
    let origin: PlaceRecord
    let destination: PlaceRecord
    let transport: String
    let distance_meters: Double
    let expected_travel_time_seconds: Double
    let advisory_notices: [String]
}

@main
struct AppleMapsBridge {
    static let asyncTimeoutSeconds: TimeInterval = 15
    static let encoder: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys]
        return encoder
    }()

    static func main() async {
        do {
            let arguments = Array(CommandLine.arguments.dropFirst())
            guard arguments.count == 2 else {
                throw BridgeFailure(errorCode: "USAGE_ERROR", message: "Expected a command and a JSON payload.", suggestion: "Pass search-places or directions with a JSON object.")
            }
            let command = arguments[0]
            let payload = try decodeJSONObject(arguments[1])
            let data = try await handle(command: command, payload: payload)
            FileHandle.standardOutput.write(data)
        } catch let failure as BridgeFailure {
            writeErrorAndExit(failure)
        } catch {
            writeErrorAndExit(BridgeFailure(errorCode: "UNEXPECTED_ERROR", message: String(describing: error), suggestion: "Retry the Apple Maps request."))
        }
    }

    static func handle(command: String, payload: [String: Any]) async throws -> Data {
        switch command {
        case "search-places":
            let query = try string(payload["query"], field: "query")
            let limit = try int(payload["limit"], field: "limit", defaultValue: 5)
            let places = try await searchPlaces(query: query, limit: limit)
            return try encoder.encode(PlaceListPayload(places: places))
        case "directions":
            let originQuery = try string(payload["origin"], field: "origin")
            let destinationQuery = try string(payload["destination"], field: "destination")
            let transport = try string(payload["transport"], field: "transport")
            let route = try await directions(originQuery: originQuery, destinationQuery: destinationQuery, transport: transport)
            return try encoder.encode(route)
        default:
            throw BridgeFailure(errorCode: "UNKNOWN_COMMAND", message: "Unknown command '\(command)'.", suggestion: "Use search-places or directions.")
        }
    }

    static func searchPlaces(query: String, limit: Int) async throws -> [PlaceRecord] {
        let request = MKLocalSearch.Request()
        request.naturalLanguageQuery = query
        let search = MKLocalSearch(request: request)
        let response = try await withTimeout(
            errorCode: "SEARCH_TIMEOUT",
            message: "Apple Maps search timed out.",
            suggestion: "Retry the query, or confirm Maps services are available on this Mac."
        ) {
            try await search.start()
        }
        let items = response.mapItems.prefix(limit)
        return items.map(placeRecord)
    }

    static func directions(originQuery: String, destinationQuery: String, transport: String) async throws -> DirectionsPayload {
        let originItem = try await resolveFirstMapItem(query: originQuery)
        let destinationItem = try await resolveFirstMapItem(query: destinationQuery)

        let request = MKDirections.Request()
        request.source = originItem
        request.destination = destinationItem
        request.transportType = transportType(transport)

        let directions = MKDirections(request: request)
        let routeResponse = try await withTimeout(
            errorCode: "DIRECTIONS_TIMEOUT",
            message: "Apple Maps directions timed out.",
            suggestion: "Retry the request, or confirm Maps services are available on this Mac."
        ) {
            try await directions.calculate()
        }

        guard let route = routeResponse.routes.first else {
            throw BridgeFailure(errorCode: "ROUTE_NOT_FOUND", message: "Apple Maps did not return a route.", suggestion: "Try a different transport mode or place query.")
        }

        return DirectionsPayload(
            origin: placeRecord(originItem),
            destination: placeRecord(destinationItem),
            transport: transport,
            distance_meters: route.distance,
            expected_travel_time_seconds: route.expectedTravelTime,
            advisory_notices: route.advisoryNotices
        )
    }

    static func resolveFirstMapItem(query: String) async throws -> MKMapItem {
        let request = MKLocalSearch.Request()
        request.naturalLanguageQuery = query
        let search = MKLocalSearch(request: request)
        let response = try await withTimeout(
            errorCode: "SEARCH_TIMEOUT",
            message: "Apple Maps search timed out.",
            suggestion: "Retry the query, or confirm Maps services are available on this Mac."
        ) {
            try await search.start()
        }
        guard let item = response.mapItems.first else {
            throw BridgeFailure(errorCode: "PLACE_NOT_FOUND", message: "Apple Maps did not find a matching place.", suggestion: "Use a more specific address or place name.")
        }
        return item
    }

    static func placeRecord(_ item: MKMapItem) -> PlaceRecord {
        let placemark = item.placemark
        let formattedAddress = [placemark.subThoroughfare, placemark.thoroughfare, placemark.locality, placemark.administrativeArea, placemark.postalCode]
            .compactMap { $0 }
            .joined(separator: " ")

        return PlaceRecord(
            name: item.name ?? placemark.name ?? "Unknown",
            address: formattedAddress.isEmpty ? nil : formattedAddress,
            latitude: placemark.coordinate.latitude,
            longitude: placemark.coordinate.longitude,
            phone: item.phoneNumber,
            url: item.url?.absoluteString
        )
    }

    static func transportType(_ value: String) -> MKDirectionsTransportType {
        switch value.lowercased() {
        case "walking":
            return .walking
        case "transit":
            return .transit
        default:
            return .automobile
        }
    }

    static func decodeJSONObject(_ raw: String) throws -> [String: Any] {
        guard
            let data = raw.data(using: .utf8),
            let payload = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        else {
            throw BridgeFailure(errorCode: "INVALID_INPUT", message: "Expected a JSON object payload.", suggestion: "Pass a valid JSON object.")
        }
        return payload
    }

    static func string(_ value: Any?, field: String) throws -> String {
        guard let text = value as? String, !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            throw BridgeFailure(errorCode: "INVALID_INPUT", message: "\(field) must be a non-empty string.", suggestion: "Provide the missing field.")
        }
        return text
    }

    static func int(_ value: Any?, field: String, defaultValue: Int) throws -> Int {
        if value == nil {
            return defaultValue
        }
        if let number = value as? Int {
            return number
        }
        if let number = value as? NSNumber {
            return number.intValue
        }
        throw BridgeFailure(errorCode: "INVALID_INPUT", message: "\(field) must be an integer.", suggestion: "Provide a numeric limit.")
    }

    static func withTimeout<T>(
        errorCode: String,
        message: String,
        suggestion: String?,
        operation: @escaping @Sendable () async throws -> T
    ) async throws -> T {
        try await withThrowingTaskGroup(of: T.self) { group in
            group.addTask {
                try await operation()
            }
            group.addTask {
                let duration = UInt64(asyncTimeoutSeconds * 1_000_000_000)
                try await Task.sleep(nanoseconds: duration)
                throw BridgeFailure(errorCode: errorCode, message: message, suggestion: suggestion)
            }
            guard let result = try await group.next() else {
                throw BridgeFailure(errorCode: errorCode, message: message, suggestion: suggestion)
            }
            group.cancelAll()
            return result
        }
    }

    static func writeErrorAndExit(_ failure: BridgeFailure) -> Never {
        let payload = ErrorPayload(error_code: failure.errorCode, message: failure.message, suggestion: failure.suggestion)
        if let data = try? encoder.encode(payload) {
            FileHandle.standardError.write(data)
        }
        exit(1)
    }
}
