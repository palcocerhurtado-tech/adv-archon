from adv_archon.desktop.branding import (
    desktop_stylesheet,
    logo_full_path,
    logo_path,
    report_logo_path,
)


def test_logo_path_points_to_packaged_brand_asset() -> None:
    path = logo_path()

    assert path.name == "archon-logo.png"
    assert path.exists()
    assert logo_full_path().exists()
    assert report_logo_path().exists()


def test_desktop_stylesheet_contains_brand_colors() -> None:
    stylesheet = desktop_stylesheet()

    assert "#050505" in stylesheet
    assert "#F7F7F4" in stylesheet
    assert "#B8B6AE" in stylesheet
    assert "#2E2E2C" in stylesheet
    assert "#C9A227" in stylesheet
    assert "Libre Baskerville" in stylesheet
    assert "Inter" in stylesheet
