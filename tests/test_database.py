from linua_updater.core.database import DLCDatabase


def test_catalog_has_109_entries():
    db = DLCDatabase()
    assert len(db.all()) == 109


def test_size_enrichment_from_estimates():
    db = DLCDatabase()
    assert db.all()["EP01"]["size"] == 1900000000
    assert db.all()["EP21"]["size"] == 2553349168
    assert "size" not in db.all()["SP70"]


def test_get():
    db = DLCDatabase()
    assert db.get("EP01")["name"] == "Get to Work"
    assert db.get("DOES_NOT_EXIST") is None