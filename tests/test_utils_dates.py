# tests/test_utils_dates.py
import utils
from database import DB_DATETIME_FORMAT, LEGACY_DATETIME_FORMAT, DISPLAY_FORMAT
import datetime


def test_parse_db_datetime_to_display_iso():
    """
    Garante que uma data no formato ISO (DB_DATETIME_FORMAT) é
    convertida corretamente para DISPLAY_DATE_FORMAT.
    """
    dt = datetime.datetime(2025, 12, 31, 23, 59, 59)
    raw = dt.strftime(DB_DATETIME_FORMAT)

    result = utils.parse_db_datetime_to_display(raw)
    assert result == dt.strftime(DISPLAY_FORMAT)  # dd/mm/YYYY


def test_parse_db_datetime_to_display_legacy():
    """
    Garante que uma data no formato legado (dd/mm/YYYY HH:MM:SS)
    continua sendo interpretada corretamente.
    """
    dt = datetime.datetime(2024, 1, 15, 10, 30, 0)
    raw = dt.strftime(LEGACY_DATETIME_FORMAT)

    result = utils.parse_db_datetime_to_display(raw)
    assert result == dt.strftime(DISPLAY_FORMAT)


def test_parse_db_datetime_to_display_invalida():
    """
    Se a string não bater com nenhum formato,
    a função deve devolver o valor original (ou algo próximo),
    mas não deve quebrar.
    """
    raw = "valor_totalmente_estranho"
    result = utils.parse_db_datetime_to_display(raw)
    # aqui só garantimos que NÃO explodiu, e retornou algo não vazio
    assert isinstance(result, str)
    assert result != ""
