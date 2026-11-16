import pytest

from skills.matcher import SkillDef, SkillMatcher
from skills.service import load_seed


@pytest.fixture(scope="module")
def m() -> SkillMatcher:
    return SkillMatcher(load_seed())


def test_aliases_map_to_canonical(m):
    assert m.find("Strong in JS and ReactJS") == ["JavaScript", "React"]
    assert "JavaScript" in m.find("ECMAScript 2020")


def test_case_insensitive(m):
    assert "Python" in m.find("experience with PYTHON or python3")
    assert "PostgreSQL" in m.find("postgres")


def test_java_not_matched_inside_javascript(m):
    found = m.find("We use JavaScript heavily")
    assert "JavaScript" in found and "Java" not in found


def test_c_family_kept_apart(m):
    assert m.find("C++ only") == ["C++"]
    assert m.find("C# and .NET") == ["C#", ".NET"]
    found = m.find("Proficient in C/C++")
    assert "C" in found and "C++" in found


def test_common_words_need_capitalization(m):
    assert "REST API" not in m.find("the rest of the team")
    assert "Microsoft Excel" not in m.find("you will excel in a fast-paced role")
    assert "Go" not in m.find("ready to go the extra mile")
    assert "REST API" in m.find("build REST services")
    assert "Go" in m.find("Backend in Go or Golang")


def test_word_boundaries(m):
    assert "R" not in m.find("R&D department")
    assert "Scala" not in m.find("scalable systems")
    assert "SQL" in m.find("SQL, NoSQL")


def test_multiword_alias_with_hyphen_or_space(m):
    assert "OOP" in m.find("object-oriented programming")
    assert "Problem Solving" in m.find("strong problem-solving skills")


def test_node_js_variants(m):
    for text in ("Node.js", "NodeJS", "node js"):
        assert "Node.js" in m.find(text), text


def test_normalize_list(m):
    assert m.normalize_list(["js", "React.js", "javascript", "Basket weaving"]) == [
        "JavaScript", "React", "Basket weaving"]


def test_custom_skill():
    m = SkillMatcher([SkillDef(name="Odoo", aliases=["OpenERP"])])
    assert m.find("Odoo/OpenERP customisation") == ["Odoo"]
