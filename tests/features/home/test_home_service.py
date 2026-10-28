from features.home.home_service import MhHomeService


def test_name_returns_company_name() -> None:
    home_service = MhHomeService()
    assert home_service.name == "MH Company"
