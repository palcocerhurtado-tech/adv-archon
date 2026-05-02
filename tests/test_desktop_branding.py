from adv_archon.desktop.branding import desktop_stylesheet, logo_path


def test_logo_path_points_to_packaged_brand_asset() -> None:
    path = logo_path()

    assert path.name == "archon-logo.png"
    assert path.exists()


def test_desktop_stylesheet_contains_brand_colors() -> None:
    stylesheet = desktop_stylesheet()

    assert "#09090B" in stylesheet
    assert "#F4F4F6" in stylesheet
    assert "#22C55E" in stylesheet
    assert "#1F1F24" in stylesheet
    assert "#3B6FFF" in stylesheet
