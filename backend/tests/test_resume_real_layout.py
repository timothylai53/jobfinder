"""A real-world resume LAYOUT with entirely invented content (fake person, schools, companies, projects, grades).

Line breaks as a PDF's extracted text gives them: " - " separators with dates at the END of the
header line, unbulleted wrapped prose, singular headings (PROJECT, ACHIEVEMENT), SKILLS sub-lines,
RESEARCH & PUBLICATIONS, EXTRACURRICULAR ACTIVITIES and a REFERENCE section.
"""
from pathlib import Path

import pytest

from resume_parser.items import join_wrapped, parse_items
from resume_parser.sections import parse_resume_text
from skills.matcher import SkillMatcher
from skills.service import load_seed

FIXTURE = Path(__file__).parent / "fixtures" / "resume_layout_real.txt"


@pytest.fixture(scope="module")
def m():
    return SkillMatcher(load_seed())


@pytest.fixture(scope="module")
def draft(m):
    return parse_resume_text(FIXTURE.read_text(encoding="utf-8"), m)


def of(draft, t):
    return [i for i in draft["items"] if i["type"] == t]


def test_fixture_contacts_are_fake():
    """Only example.* addresses and all-zero phone numbers (the real-name check ran when the fixture was made)."""
    import re

    text = FIXTURE.read_text(encoding="utf-8")
    assert all(e.split("@")[1].startswith("example.") for e in re.findall(r"[\w.+-]+@[\w.-]+", text))
    for phone in re.findall(r"\b0\d{1,2}-\d{6,8}\b", text):
        assert set(phone.split("-")[1]) <= {"0", "1"}, phone
    assert all("example" in u for u in re.findall(r"https?://\S+", text))


def test_education(draft):
    degree, diploma = of(draft, "education")
    assert (degree["title"], degree["organization"], degree["start"], degree["end"]) == (
        "Bachelor of Science with Honours (Information Technology)", "Universiti Contoh Malaysia (UCM), Perlis",
        "Sep 2023", "Present")
    assert degree["bullets"] == ["GPA : 3.52 | GCPA: 3.61", "Major: Software Engineering"]
    assert (diploma["title"], diploma["organization"], diploma["start"], diploma["end"], diploma["bullets"]) == (
        "Diploma in Information Technology", "Kolej Contoh Vocational", "June 2020", "April 2022", ["GCPA: 3.70"])
    p = draft["profile"]
    assert (p["education_level"], p["education_field"], p["degree_status"]) == ("Degree", "Software Engineering", "in_progress")
    assert [c["title"] for c in of(draft, "certification")] == ["MUET: Band 4.0"]


def test_projects(draft):
    clinic, library, parking = of(draft, "project")
    assert (clinic["title"], clinic["organization"]) == ("Web-Based Clinic Booking System", "Final Year Project (Silver Award)")
    assert library["title"] == "Web-Based Library Loan System" and library["organization"] == ""
    assert parking["title"] == "Real-Time Parking Availability System"
    # tech line -> skills (unknown tools kept as written), never organization or bullet
    assert clinic["skills"][:7] == ["Vue.js", "Node.js", "MongoDB", "REST API", "DigitalOcean", "SendGrid API", "Stripe API"]
    assert {"Angular", "Java", "Spring Boot", "Playwright", "Jenkins", "CI/CD"} <= set(library["skills"])
    assert {"Java", "OOP", "Data Structures and Algorithms"} <= set(parking["skills"])
    # wrapped prose -> exactly one bullet per project
    assert clinic["bullets"] == ["Architected an integrated full-stack application streamlining appointment booking, dynamic doctor "
                                 "schedules, and patient administration for small neighbourhood clinics, successfully deployed on "
                                 "DigitalOcean cloud infrastructure."]
    assert len(library["bullets"]) == 1 and library["bullets"][0].endswith("automated Jenkins CI/CD deployment pipeline.")
    assert len(parking["bullets"]) == 1 and "Object-Oriented Programming principles" in parking["bullets"][0]


def test_work(draft):
    web, desk, clerk = of(draft, "work")
    assert (web["title"], web["organization"], web["start"], web["end"]) == ("Freelance Web Designer (Part-Time)", "", "Jan 2020", "Jan 2022")
    assert (desk["title"], desk["organization"], desk["start"], desk["end"]) == (
        "Helpdesk Assistant (Intern)", "Contoh Rangkai Sdn Bhd, Kuantan", "Mar 2022", "Jul 2022")
    assert (clerk["title"], clerk["organization"], clerk["start"], clerk["end"]) == (
        "Admin Clerk (Full Time)", "Kedai Contohh, Kuantan", "Aug 2022", "Sep 2023")
    assert len(web["bullets"]) == 1 and web["bullets"][0].endswith("site optimization for clients.")
    assert len(desk["bullets"]) == 1
    assert clerk["bullets"] == [
        "Provided basic support for office computers and printers while managing the office supply and inventory.",
        "Performed data entry for daily orders and prepared detailed weekly sales summaries using Microsoft Excel."]


def test_achievements_publication_and_activities(draft):
    ach = of(draft, "achievement")
    titles = [a["title"] for a in ach]
    assert titles[:4] == [f"Faculty Of Computing Dean’s List Award Semester {s}" for s in (
        "S1 Session 2023/2024", "S2 Session 2024/2025", "S3 Session 2024/2025", "S4 Session 2025/2026")]
    assert titles[4] == "High Academic Achiever (Diploma)"
    assert ach[4]["bullets"] == ["Consistently maintained a CGPA of 3.50 or above in every semester"]
    champion = ach[5]
    assert champion["title"].startswith("Champion, Contoh Skills Competition") and champion["title"].endswith(
        "IT Network & System Administration (2019)") and champion["end"] == "2019"  # wrapped line joined
    assert titles[6:9] == ["Best IT Skills Award, Graduation Ceremony, Kolej Contoh Vocational (2022)",
                           "Placed in the top 10 and received a Silver Award in the Contoh Innovation competition",
                           "Participant, Contoh Code Hackathon 2026"]
    assert ach[8]["bullets"] == ["Showcased rapid full-stack prototyping and problem-solving skills under strict time constraints"]

    (pub,) = of(draft, "publication")
    assert (pub["title"], pub["organization"], pub["end"]) == (
        "Web-based Booking System for Small Clinics", "Contoh Computing Symposium (CCS) 2025", "2025")
    assert pub["bullets"][0].startswith("Nurul A.B.C (2025, June 3).") and pub["bullets"][0].endswith("(CCS) Berhad.")

    band = ach[9]
    assert (band["title"], band["organization"]) == ("Photography Club Member, UCM Campus Events", "University Level")
    assert band["bullets"] == ["(Contoh Nite, Sports Day, Open Day, Convocation UCM, Culture Week)"]
    assert len(ach) == 10


def test_skills_languages_and_references(draft):
    p = draft["profile"]
    assert {"Java", "JavaScript", "TypeScript", "PHP", "SQL", "Spring Boot", "Angular", "Vue.js", "Docker", "Git",
            "MySQL", "Jenkins", "Selenium", "JUnit", "Playwright", "Figma"} <= set(p["skills"])
    assert p["languages"] == ["Bahasa Malaysia", "English", "Mandarin"]
    assert draft["skipped_sections"] == ["references"]
    assert "Contohhh" not in repr(draft) and "ahmad.c@example.edu.my" not in repr(draft)
    # nothing but the PROFILE summary is left unimported (contact lines are not "unparsed")
    assert {u["section"] for u in draft["unparsed_lines"]} == {"summary"}
    assert len(draft["items"]) == 20


# ---------- rule 3: a wrapped prose line never starts a new item ----------

def test_capitalised_prose_lines_stay_in_the_item(m):
    lines = ["Data Clerk - Contoh Sdn Bhd Jan 2020 - Feb 2021",
             "Prepared weekly reports for the finance team and kept records up to",
             "Date across three branches.",
             "Handled walk-in customers.",
             "Microsoft Excel was used daily for stock counts and",
             "Reconciliation."]
    items = parse_items("work", lines, m, width=70)
    assert len(items) == 1
    assert items[0].title == "Data Clerk" and items[0].bullets == [
        "Prepared weekly reports for the finance team and kept records up to Date across three branches.",
        "Handled walk-in customers.",
        "Microsoft Excel was used daily for stock counts and Reconciliation."]


def test_header_needs_dates_dash_or_tech_line(m):
    lines = ["Shop Assistant - Kedai Contoh Jun 2019 - Dec 2019",
             "Served customers.",
             "Inventory Tracker",            # plain short line, no dates/dash/tech line: not a new item
             "Volunteer - Contoh Club 2018 - 2019",
             "Organised events."]
    items = parse_items("work", lines, m)
    assert [i.title for i in items] == ["Shop Assistant", "Volunteer"]
    assert items[0].bullets == ["Served customers.", "Inventory Tracker"]
    assert (items[1].organization, items[1].start, items[1].end) == ("Contoh Club", "2018", "2019")


def test_join_wrapped_full_width_uses_physical_line(m):
    lines = ["Short award line 2024",
             "A long achievement line that nearly fills the whole page width and wraps onto",
             "Next Line (2019).",
             "Another award"]
    assert join_wrapped(lines, width=80, matcher=m) == [
        "Short award line 2024",
        "A long achievement line that nearly fills the whole page width and wraps onto Next Line (2019).",
        "Another award"]
