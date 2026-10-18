
import os
import pytest
from tools import lookup, calculate


# LOOKUP TESTS

def test_population_2025():
    r = lookup("Ossbridge", "population_2025")
    assert r["ok"] is True
    assert r["value"] == 52904
    assert r["source_id"] == "NR-01"


def test_similar_district_names():
    a = lookup("Ossbridge", "population_2025")
    b = lookup("Ossford", "population_2025")
    assert a["value"] == 52904
    assert b["value"] == 30982
    assert a["source_id"] != b["source_id"]


def test_misspelled_district():
    r = lookup("Ossbrige", "population_2025")
    assert r["ok"] is False
    assert "Ossbridge" in r["suggestions"]


def test_archived_profiles():
    for name in ["NR-13", "NR-14"]:
        r = lookup(name, "population_2025")
        assert r["ok"] is False
        assert "Archived" in r["error"]


def test_brightwater_correction():
    r = lookup("Brightwater", "area_km2")
    assert r["ok"] is True
    assert r["value"] == 921.4
    assert r["source_id"] == "NR-16"


def test_water_units():
    r = lookup("Lindenmoor", "water_use")
    assert r["ok"] is True
    assert r["value"] == 2151400
    assert r["unit"] == "cubic metres"


def test_water_tariff():
    r = lookup("region", "water_tariff")
    assert r["ok"] is True
    assert r["value"] == pytest.approx(142.35)


def test_unknown_field():
    r = lookup("Ossbridge", "temperature")
    assert r["ok"] is False


def test_unknown_district():
    r = lookup("UnknownDistrict", "population_2025")
    assert r["ok"] is False


# CALCULATOR TESTS

def test_basic_arithmetic():
    r = calculate("2 + 3 * 4")
    assert r["ok"] is True
    assert r["value"] == 14


def test_required_multiplication():
    r = calculate("48317 * 1.0947")
    assert r["ok"] is True
    assert r["value"] == pytest.approx(52892.6199)


def test_density_difference():
    r = calculate(
        "(37203 / 758.6) - (44675 / 921.4)"
    )
    assert r["ok"] is True
    assert r["value"] == pytest.approx(
        0.5556561156405735
    )


def test_division_by_zero():
    r = calculate("10 / 0")
    assert r["ok"] is False


def test_no_system_commands(monkeypatch):
    calls = []

    def fake_system(command):
        calls.append(command)
        return 0

    monkeypatch.setattr(os, "system", fake_system)

    r = calculate(
        "__import__('os').system('echo hi')"
    )
    assert r["ok"] is False
    assert calls == []


def test_no_attribute_access():
    r = calculate("(1).__class__")
    assert r["ok"] is False


def test_no_dangerous_exponentiation():
    r = calculate("9**9**9")
    assert r["ok"] is False


def test_reject_large_number():
    r = calculate("10000000000000000")
    assert r["ok"] is False


def test_reject_variables():
    r = calculate("unknown_variable + 2")
    assert r["ok"] is False
