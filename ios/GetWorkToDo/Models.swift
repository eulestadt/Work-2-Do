import Foundation

struct LatestResponse: Codable {
    let date: String
    let digestMd: String?
    let gameplanMd: String?
    let gameplanTomorrowMd: String?
    let items: [ScheduleItem]?
    let contextSummary714: String?

    enum CodingKeys: String, CodingKey {
        case date
        case digestMd = "digest_md"
        case gameplanMd = "gameplan_md"
        case gameplanTomorrowMd = "gameplan_tomorrow_md"
        case items
        case contextSummary714 = "context_summary_7_14"
    }
}

struct ScheduleItem: Identifiable, Codable {
    let id: String
    let course: String
    let date: String
    let type: String
    let title: String
    let description: String
    let url: String
    let isMajor: Bool
    let completed: Bool?

    enum CodingKeys: String, CodingKey {
        case id, course, date, type, title, description, url
        case isMajor = "is_major"
        case completed
    }
}

struct ManualItem: Identifiable, Codable {
    let id: String
    var title: String
    var date: String?
    var type: String
    var course: String

    init(id: String = UUID().uuidString, title: String, date: String? = nil, type: String = "other", course: String = "") {
        self.id = id
        self.title = title
        self.date = date
        self.type = type
        self.course = course
    }
}

struct TimerSession: Codable {
    let itemId: String
    let startedAt: Date
    let endedAt: Date
    var course: String?
    var date: String?

    var duration: TimeInterval { endedAt.timeIntervalSince(startedAt) }

    enum CodingKeys: String, CodingKey {
        case itemId, startedAt, endedAt, course, date
    }

    init(itemId: String, startedAt: Date, endedAt: Date, course: String? = nil, date: String? = nil) {
        self.itemId = itemId
        self.startedAt = startedAt
        self.endedAt = endedAt
        self.course = course
        self.date = date
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        itemId = try c.decode(String.self, forKey: .itemId)
        startedAt = try c.decode(Date.self, forKey: .startedAt)
        endedAt = try c.decode(Date.self, forKey: .endedAt)
        course = try c.decodeIfPresent(String.self, forKey: .course)
        date = try c.decodeIfPresent(String.self, forKey: .date)
    }

    func encode(to encoder: Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(itemId, forKey: .itemId)
        try c.encode(startedAt, forKey: .startedAt)
        try c.encode(endedAt, forKey: .endedAt)
        try c.encodeIfPresent(course, forKey: .course)
        try c.encodeIfPresent(date, forKey: .date)
    }
}
