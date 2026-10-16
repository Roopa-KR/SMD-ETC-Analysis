"""Application route checks for the ten-truck synthetic demo."""
import os

import pytest


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    os.environ["DATABASE_URL"] = "sqlite:///" + str(tmp_path_factory.mktemp("db") / "test.db").replace("\\", "/")
    import app as app_module
    return app_module.app.test_client()


def test_dashboard_shows_calculated_statuses_at_default_snapshot(client):
    html = client.get("/?snapshot=10").get_data(as_text=True)
    # v11: corrected demo data + picking-time pace -> every open truck is calculated ON TIME at 18:30
    assert "SH0908-1034" in html and "ON TIME" in html
    assert "10-minute safety buffer" in html  # conservative scenario and buffer are explained
    assert "Truck ETC" in html and "SMD · WH 100" in html
    assert "08-Sep-2026" in html and "Truck performance" in html
    assert "NULL" not in html


def test_every_snapshot_renders(client):
    for snap in range(1, 19):
        assert client.get(f"/?snapshot={snap}").status_code == 200


def test_truck_page_explains_the_status(client):
    html = client.get("/truck/SH0908-1034?snapshot=6").get_data(as_text=True)
    assert "Why this status" in html and "buffered deadline" in html
    assert "Work IDs" in html
    assert "built-in method items" not in html
    assert "Truck" in html
    assert client.get("/truck/UNKNOWN").status_code == 404


def test_removed_late_routes_are_not_available(client):
    for ship in ("SH0908-1001", "SH0908-1075", "SH0908-1085"):
        assert client.get(f"/truck/{ship}").status_code == 404


def test_truck_pages_render(client):
    for snap in (1, 6, 9, 13, 18):
        for ship in ("SH0908-1018", "SH0908-1012", "SH0908-1057", "SH0908-1069"):
            assert client.get(f"/truck/{ship}?snapshot={snap}").status_code == 200


def test_operator_profile_and_reallocation_provenance_render(client):
    profile = client.get("/operator/hgroff?snapshot=10").get_data(as_text=True)
    assert "Operator hgroff" in profile
    assert "SIMULATED PLANNING ASSUMPTION" in profile
    assert "Logged-time pace" in profile and "Planning pace" in profile   # v11 labels
    assert "picking time" in profile and "Includes waiting" in profile
    truck = client.get("/truck/SH0908-1069?snapshot=10").get_data(as_text=True)
    assert "Preview / Allocate operators" in truck
    assert "automatically suggested reallocation is disabled" in truck
    assert "SIMULATED PLANNING ASSUMPTION" in profile
    assert "reallocation-wide-table" not in truck  # no ghost automatic allocation table


def test_late_truck_and_source_safety_explained_in_planner(client):
    truck = client.get("/truck/SH0908-1069?snapshot=6").get_data(as_text=True)
    assert "buffered deadline" in truck
    planner = client.get("/planner?snapshot=10&worktype=2").get_data(as_text=True)
    assert "UNSAFE" in planner
    assert "At-risk individual picking assignments" in planner
    assert "Allocate selected operators" not in planner   # only visible with a preview
