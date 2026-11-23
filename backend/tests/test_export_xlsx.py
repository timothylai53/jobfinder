"""The Excel export reads like a spreadsheet: named headers, bold, filterable, sized columns, real dates."""
import io
from datetime import date, datetime

from openpyxl import load_workbook

JD = "Junior Developer\nRequirements:\n- Python\n- SQL"


def test_xlsx_has_readable_headers_real_dates_and_a_filter(client):
    job = client.post("/api/jobs/manual", json={"title": "Junior Developer", "company": "Syarikat Contoh Bhd",
                                                "description": JD}).json()
    app_id = client.post("/api/applications", json={"job_id": job["id"]}).json()["id"]
    client.patch(f"/api/applications/{app_id}", json={"status": "Applied", "applied_at": "2026-11-20"})
    wb = load_workbook(io.BytesIO(client.get("/api/export/xlsx").content))

    jobs = wb["Jobs"]
    head = [c.value for c in jobs[1]]
    assert head[:6] == ["ID", "Title", "Company", "Location", "Work arrangement", "Score"]
    assert "Salary min" in head and "Added" in head and "salary_min" not in head
    assert all(c.font.bold for c in jobs[1])
    assert jobs.freeze_panes == "A2" and jobs.auto_filter.ref == jobs.dimensions
    added = jobs.cell(2, head.index("Added") + 1)
    assert isinstance(added.value, datetime) and "yyyy" in added.number_format
    assert jobs.column_dimensions["B"].width >= len("Junior Developer")

    apps = wb["Applications"]
    ahead = [c.value for c in apps[1]]
    applied = apps.cell(2, ahead.index("Applied on") + 1)
    assert applied.value.date() == date(2026, 11, 20) and applied.number_format == "dd mmm yyyy"


def test_csv_keeps_its_field_names(client):
    text = client.get("/api/export/jobs.csv").content.decode("utf-8-sig")
    assert text.splitlines()[0].startswith("id,title,company,location,work_arrangement,score")
