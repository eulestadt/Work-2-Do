from datetime import date

from src.populi_scraper import parse_syllabus_html, parse_week_content_html


def test_parse_syllabus_html_extracts_rows_with_dates():
    html = """
    <table>
      <tr><th>Date</th><th>Title</th><th>Details</th></tr>
      <tr>
        <td>2/25</td>
        <td>Required reading: Chapter 3</td>
        <td>Pages 45–67</td>
      </tr>
      <tr>
        <td>3/4</td>
        <td>Paper due</td>
        <td>First draft</td>
      </tr>
    </table>
    """
    tasks = parse_syllabus_html(html, "bioethics", 2026)

    assert len(tasks) == 2
    dates = {t.date for t in tasks}
    assert date(2026, 2, 25) in dates
    assert date(2026, 3, 4) in dates


def test_parse_week_content_html_splits_by_day():
    html = """
    <div id="content_goes_here">
      <p><strong>Week overview</strong></p>
      <p>For this week's modern Greek, you will be:</p>
      <ul><li>Continuing Pimsleur.</li></ul>
      <p><strong>Everyday</strong>:</p>
      <ul><li>Do your Anki cards.</li></ul>
      <p><strong>Wednesday:</strong></p>
      <ul><li>Practice questions 1 and 2</li></ul>
      <p><strong>Friday:</strong></p>
      <ul><li>Quiz 6</li></ul>
    </div>
    """
    tasks = parse_week_content_html(
        html,
        course_code="greek",
        week_label="Week 6",
        week_start=date(2026, 2, 23),
        file_links=[("Story PDF", "https://example.com/story.pdf")],
    )
    by_date = {t.date: t for t in tasks}
    assert date(2026, 2, 25) in by_date  # Wednesday
    assert date(2026, 2, 27) in by_date  # Friday
    assert "Do your Anki cards" in by_date[date(2026, 2, 25)].description
    assert "Quiz 6" in by_date[date(2026, 2, 27)].description
    assert "Story PDF" in by_date[date(2026, 2, 27)].description

