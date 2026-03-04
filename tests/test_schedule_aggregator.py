from datetime import date

from src.models import TaskItem
from src.schedule_aggregator import aggregate_schedule


def test_next_academic_days_and_major_items():
    tasks = [
        TaskItem(
            course="micro_lab",
            date=date(2026, 2, 25),
            type="lab",
            title="Death of Microorganisms",
        ),
        TaskItem(
            course="micro_lab",
            date=date(2026, 3, 11),
            type="lab",
            title="Determination of Bacterial Numbers",
            is_major=True,
        ),
        TaskItem(
            course="phys2_lecture",
            date=date(2026, 2, 24),
            type="lecture",
            title="Electric Circuits",
        ),
        TaskItem(
            course="phys2_lecture",
            date=date(2026, 2, 24),
            type="exam",
            title="Midterm 1",
            is_major=True,
        ),
    ]

    today = date(2026, 2, 24)
    meeting_patterns = {
        "micro_lab": "W",
        "phys2_lecture": "T",
    }
    per_course_dates, per_course, major_items = aggregate_schedule(
        today, tasks, meeting_patterns
    )

    # phys2_lecture (T): today is Tue 2/24 -> prev = Tue before today (2/17), next = 2/24 + 3/3
    assert per_course_dates["phys2_lecture"] == [
        date(2026, 2, 17),
        date(2026, 2, 24),
        date(2026, 3, 3),
    ]
    # micro_lab (W): today Tue 2/24 -> prev Wed 2/18, next Wed 2/25 + 3/4 (look back + look ahead)
    assert per_course_dates["micro_lab"] == [
        date(2026, 2, 18),
        date(2026, 2, 25),
        date(2026, 3, 4),
    ]

    assert "phys2_lecture" in per_course
    assert date(2026, 2, 24) in per_course["phys2_lecture"]
    assert len(per_course["phys2_lecture"][date(2026, 2, 24)]) == 2

    assert "micro_lab" in per_course
    assert date(2026, 2, 25) in per_course["micro_lab"]

    # Major items within 21 days from today should include Midterm 1 and possibly others
    major_titles = {item.title for item in major_items}
    assert "Midterm 1" in major_titles

