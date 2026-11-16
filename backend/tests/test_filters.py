import pytest

from filters.engine import JobView, Rule, check_rule, evaluate


def job(**kw):
    base = dict(title="Software Engineer", company="Acme Sdn Bhd", description="Python, SQL. 1 year of experience.")
    base.update(kw)
    return JobView(**base)


def test_title_contains_any_term_word_boundary():
    r = Rule(1, "title_contains", "Senior, Lead, Manager")
    assert check_rule(r, job(title="Senior Backend Engineer")) == 'Title contains "Senior"'
    assert check_rule(r, job(title="Team lead (Java)")) == 'Title contains "Lead"'
    assert check_rule(r, job(title="Leading-edge Graduate Program")) is None
    assert check_rule(r, job(title="Junior Developer")) is None


def test_company_equals_ignores_suffixes_and_case():
    r = Rule(1, "company_equals", "Shady Recruiters, Acme")
    assert check_rule(r, job(company="ACME SDN. BHD.")) == "Company is Acme"
    assert check_rule(r, job(company="Acme Labs")) is None


def test_keyword_in_jd():
    r = Rule(1, "keyword_in_jd", "commission only, MLM")
    assert check_rule(r, job(description="This is a commission only role")) == 'JD mentions "commission only"'
    assert check_rule(r, job()) is None


def test_min_years_over():
    r = Rule(1, "min_years_over", "2")
    assert check_rule(r, job(description="Requirements:\n- Minimum 3 years of experience")) == "Requires 3 years (> 2)"
    assert check_rule(r, job(description="Requirements:\n- 2 years of experience")) is None
    assert check_rule(r, job(description="No years stated")) is None
    # Preferred-only years do not count.
    assert check_rule(r, job(description="5 years of experience is a plus")) is None


def test_min_salary_below_unknown_salary_not_hidden():
    r = Rule(1, "min_salary_below", "3000")
    assert check_rule(r, job(salary_min=2000, salary_max=2500)) == "Salary 2500 below 3000"
    assert check_rule(r, job(salary_min=2500, salary_max=3500)) is None
    assert check_rule(r, job(salary_min=2800)) == "Salary 2800 below 3000"
    assert check_rule(r, job()) is None


def test_disabled_rules_skipped_and_reasons_joined():
    rules = [Rule(1, "title_contains", "Senior"), Rule(2, "keyword_in_jd", "Python"), Rule(3, "keyword_in_jd", "SQL", enabled=False)]
    assert evaluate(rules, job(title="Senior Dev")) == 'Title contains "Senior"; JD mentions "Python"'
    assert evaluate([rules[2]], job()) is None


def test_unknown_type_raises():
    with pytest.raises(ValueError):
        check_rule(Rule(1, "bogus", "x"), job())
