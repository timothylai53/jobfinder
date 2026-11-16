"""Location matching with the editable state -> towns/areas map."""
import pytest

from app.settings_store import default_location_map
from matcher.rules import location_matches
from matcher.scoring import Candidate, score_job
from skills.matcher import SkillMatcher
from skills.service import load_seed

MAP = default_location_map()


def test_seed_covers_every_state_and_territory():
    expected = {"Johor", "Kedah", "Kelantan", "Melaka", "Negeri Sembilan", "Pahang", "Penang", "Perak", "Perlis",
                "Sabah", "Sarawak", "Selangor", "Terengganu", "Kuala Lumpur", "Putrajaya", "Labuan"}
    assert expected <= set(MAP)
    assert all(MAP[s] for s in expected if s != "Putrajaya")


@pytest.mark.parametrize("job_location,state,town", [
    ("Cyberjaya, Selangor", "Selangor", "Cyberjaya"),
    ("Shah Alam", "Selangor", "Shah Alam"),
    ("Petaling Jaya", "Selangor", "Petaling Jaya"),
    ("Puchong, Malaysia", "Selangor", "Puchong"),
    ("Klang", "Selangor", "Klang"),
    ("Bangsar South, Kuala Lumpur", "Kuala Lumpur", "Bangsar South"),  # longest name wins
    ("Mont Kiara", "Kuala Lumpur", "Mont Kiara"),
    ("Bukit Jalil", "Kuala Lumpur", "Bukit Jalil"),
    ("KL", "Kuala Lumpur", "KL"),
    ("Kota Kinabalu", "Sabah", "Kota Kinabalu"),
    ("Kuching, Sarawak", "Sarawak", "Sarawak"),
    ("Bayan Lepas", "Penang", "Bayan Lepas"),
    ("Johor Bahru", "Johor", "Johor Bahru"),
    ("Ipoh, Perak", "Perak", "Perak"),
])
def test_state_matches_its_towns(job_location, state, town):
    hit = location_matches(job_location, [state], MAP)
    assert hit is not None and hit[0] == state
    assert hit[1].lower() == town.lower()


def test_whole_word_only():
    # "KL" must not match "Klang", and Klang (Selangor) is not Kuala Lumpur
    assert location_matches("Klang", ["Kuala Lumpur"], MAP) is None
    assert location_matches("Subang Jaya", ["Kuala Lumpur"], MAP) is None


def test_other_state_does_not_match():
    assert location_matches("Kuching", ["Selangor", "Kuala Lumpur"], MAP) is None
    assert location_matches("Penang", ["Johor"], MAP) is None


def test_aliases_and_case():
    assert location_matches("Kuala Lumpur", ["kl"], MAP)[0] == "kl"
    assert location_matches("George Town", ["pulau pinang"], MAP) is not None  # alias -> Penang -> towns
    assert location_matches("Melaka City", ["Malacca"], MAP) is not None
    assert location_matches("CYBERJAYA", ["selangor"], MAP) is not None


def test_town_preference_does_not_expand():
    # Preferring a town matches that town only, not the whole state
    assert location_matches("Petaling Jaya", ["Petaling Jaya"], MAP) is not None
    assert location_matches("Shah Alam", ["Petaling Jaya"], MAP) is None


def test_edited_map_and_no_map():
    custom = {"Selangor": ["Cyberjaya"]}
    assert location_matches("Cyberjaya", ["Selangor"], custom) is not None
    assert location_matches("Puchong", ["Selangor"], custom) is None
    assert location_matches("Cyberjaya", ["Selangor"], None) is None
    assert location_matches("Selangor", ["Selangor"], None) is not None


def test_breakdown_names_the_matched_town():
    me = Candidate(preferred_locations=["Selangor"], location_map=MAP)
    r = score_job("Requirements:\n- Python", "Cyberjaya", me, SkillMatcher(load_seed()))
    loc = next(i for c in r["categories"] for i in c["items"] if i["name"].startswith("Location"))
    assert loc["status"] == "met" and loc["detail"] == "matches Selangor (Cyberjaya)"


def test_settings_api_edits_map_and_rescores(client):
    p = client.get("/api/profile").json()
    p["preferred_locations"] = ["Selangor"]
    client.put("/api/profile", json=p)
    jid = client.post("/api/jobs/manual", json={"title": "Dev", "location": "Puchong",
                                                "description": "Requirements:\n- Python"}).json()["id"]

    def loc_status():
        bd = client.get(f"/api/jobs/{jid}").json()["match"]["breakdown"]
        return next(i for c in bd["categories"] for i in c["items"] if i["name"].startswith("Location"))["status"]

    assert loc_status() == "met"
    s = client.get("/api/settings").json()
    assert "Puchong" in s["locations"]["Selangor"]
    s["locations"]["Selangor"] = [t for t in s["locations"]["Selangor"] if t != "Puchong"]
    client.put("/api/settings", json=s)
    assert "Puchong" not in client.get("/api/settings").json()["locations"]["Selangor"]
    assert loc_status() == "not_met"
    assert client.get("/api/settings/locations/defaults").json() == MAP
