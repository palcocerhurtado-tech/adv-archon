from adv_archon.desktop.branding import desktop_stylesheet, logo_path


def test_logo_path_points_to_packaged_brand_asset() -> None:
    path = logo_path()

    assert path.name == "archon-logo.png"
    assert path.exists()


def test_desktop_stylesheet_contains_brand_colors() -> None:
    stylesheet = desktop_stylesheet()

    assert "#0B0C0E" in stylesheet
    assert "#F6F7FB" in stylesheet
    assert "#78FF6B" in stylesheet
    assert "#1C1F24" in stylesheet
    assert "#FF4FD8" in stylesheet

