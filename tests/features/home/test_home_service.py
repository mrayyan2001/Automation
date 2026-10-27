from features.home.home_service import MznHomeService


def test_name_returns_company_name() -> None:
    home_service = MznHomeService()
    assert home_service.name == "MZN Company"


def test_tags_returns_company_tags() -> None:
    home_service = MznHomeService()
    assert home_service.tags == ["IT", "AI"]
