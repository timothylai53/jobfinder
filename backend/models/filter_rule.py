from sqlmodel import Field, SQLModel

FILTER_TYPES = ("title_contains", "title_must_contain_one_of", "company_equals", "min_years_over", "min_salary_below",
                "keyword_in_jd")


class FilterRuleBase(SQLModel):
    type: str
    value: str
    action: str = "hide"
    enabled: bool = True


class FilterRule(FilterRuleBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
