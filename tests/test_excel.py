import pytest
import openpyxl
from unittest.mock import patch


def _make_excel(tmp_path, rows, headers=("PLACAS", "FACTOR")):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(list(headers))
    for row in rows:
        ws.append(list(row))
    path = str(tmp_path / "test.xlsx")
    wb.save(path)
    return path


def test_read_plates_sample(monkeypatch, tmp_path):
    monkeypatch.setenv("RENEWAL_PLATE_FIELD", "PLACAS")
    plates = [f"PL{i:04d}" for i in range(100)]
    path = _make_excel(tmp_path, [(p, 0.022) for p in plates])

    from checks.excel import read_plates
    result = read_plates(path, sample_size=10)

    assert len(result) == 10
    assert all(p in plates for p in result)


def test_read_plates_fewer_than_sample(monkeypatch, tmp_path):
    monkeypatch.setenv("RENEWAL_PLATE_FIELD", "PLACAS")
    path = _make_excel(tmp_path, [("ABC123", 0.022), ("DEF456", 0.022)])

    from checks.excel import read_plates
    result = read_plates(path, sample_size=50)

    assert len(result) == 2


def test_read_plates_skips_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("RENEWAL_PLATE_FIELD", "PLACAS")
    path = _make_excel(tmp_path, [("ABC123", 0.022), ("", 0.022), (None, 0.022)])

    from checks.excel import read_plates
    result = read_plates(path, sample_size=10)

    assert len(result) == 1
    assert result[0] == "ABC123"


def test_read_plates_missing_column(monkeypatch, tmp_path):
    monkeypatch.setenv("RENEWAL_PLATE_FIELD", "PLACAS")
    path = _make_excel(tmp_path, [("GTF2294", 0.022)], headers=("MATRICULA", "FACTOR"))

    from checks.excel import read_plates
    with pytest.raises(ValueError, match="PLACAS"):
        read_plates(path, sample_size=5)


def test_read_plates_uses_env_sample_size(monkeypatch, tmp_path):
    monkeypatch.setenv("RENEWAL_PLATE_FIELD", "PLACAS")
    monkeypatch.setenv("QA_SAMPLE_SIZE", "3")
    plates = [f"PL{i:04d}" for i in range(20)]
    path = _make_excel(tmp_path, [(p, 0.022) for p in plates])

    from checks.excel import read_plates
    result = read_plates(path, sample_size=None)

    assert len(result) == 3
