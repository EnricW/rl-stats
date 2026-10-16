"""Tests del agrupado en sesiones de juego."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from pipeline.sessions import group_sessions, is_closed, local_tz, session_of

MADRID = ZoneInfo("Europe/Madrid")


def _m(id_, date, duration=300):
    return {"id": id_, "date": date, "duration": duration}


def test_hueco_grande_parte_la_sesion():
    sessions = group_sessions([
        _m("a", "2026-10-14T20:00:00Z"),
        _m("b", "2026-10-14T20:10:00Z"),   # +10 min: misma sesión
        _m("c", "2026-10-15T20:00:00Z"),   # +24 h: otra
    ], gap_hours=5)
    assert [s["games"] for s in sessions] == [2, 1]
    assert [s["match_ids"] for s in sessions] == [["a", "b"], ["c"]]


def test_hueco_de_dos_horas_no_parte():
    # una pausa para cenar no debe cortar la noche en dos informes
    sessions = group_sessions([
        _m("a", "2026-10-14T18:00:00Z"),
        _m("b", "2026-10-14T20:00:00Z"),
    ], gap_hours=5)
    assert len(sessions) == 1 and sessions[0]["games"] == 2


def test_partidas_solapadas_son_una_sesion():
    # los datos reales traen pares que se solapan unos segundos: `date` es el
    # inicio y `duration` no siempre es disjunta
    sessions = group_sessions([
        _m("a", "2026-10-15T21:04:32Z", duration=886),   # acaba 21:19:18
        _m("b", "2026-10-15T21:12:27Z", duration=359),   # empieza antes
    ], gap_hours=5)
    assert len(sessions) == 1
    assert sessions[0]["end"] == "2026-10-15T21:19:18Z"  # el máximo, no el último


def test_duration_ausente_no_revienta():
    sessions = group_sessions([
        {"id": "a", "date": "2026-10-14T20:00:00Z"},            # sin duration
        {"id": "b", "date": "2026-10-14T20:30:00Z", "duration": None},
    ], gap_hours=5)
    assert len(sessions) == 1 and sessions[0]["games"] == 2


def test_cruce_de_medianoche_sigue_siendo_una_sesion():
    sessions = group_sessions([
        _m("a", "2026-10-15T21:40:00Z", duration=600),
        _m("b", "2026-10-15T22:30:00Z"),
        _m("c", "2026-10-16T00:10:00Z"),   # ya es otro día, misma tanda
    ], gap_hours=5, tz=MADRID)
    assert len(sessions) == 1
    assert sessions[0]["games"] == 3
    # se etiqueta con la fecha de la PRIMERA partida (en hora local)
    assert sessions[0]["date"] == "2026-10-15"


def test_la_fecha_es_local_no_utc():
    # 22:30 UTC del 14 son las 00:30 del 15 en Madrid: la etiqueta debe decir
    # el día que percibe el usuario
    [s] = group_sessions([_m("a", "2026-10-14T22:30:00Z")], tz=MADRID)
    assert s["date"] == "2026-10-15"
    assert s["id"] == "2026-10-15-0030"


def test_el_id_no_se_desplaza_al_aparecer_otra_sesion():
    primera = group_sessions([_m("a", "2026-10-14T19:00:00Z")], tz=MADRID)[0]
    luego = group_sessions([
        _m("a", "2026-10-14T19:00:00Z"),
        _m("b", "2026-10-14T06:00:00Z"),   # replay tardío, sesión ANTERIOR
    ], tz=MADRID)
    ids = [s["id"] for s in luego]
    # el id de la sesión ya informada sigue siendo el mismo (lleva su hora)
    assert primera["id"] in ids
    assert ids == sorted(ids)  # orden cronológico


def test_is_closed():
    now = datetime(2026, 10, 15, 2, 0, tzinfo=UTC)
    abierta = {"end": (now - timedelta(hours=1)).isoformat()}
    cerrada = {"end": (now - timedelta(hours=6)).isoformat()}
    assert is_closed(abierta, 5, now=now) is False
    assert is_closed(cerrada, 5, now=now) is True


def test_local_tz_y_session_of():
    assert local_tz({"timezone": "Europe/Madrid"}) == MADRID
    assert local_tz({}) == UTC
    assert local_tz({"timezone": "Marte/Olympus"}) == UTC  # inválida -> UTC
    sessions = group_sessions([_m("a", "2026-10-14T20:00:00Z")])
    assert session_of(sessions, "a")["games"] == 1
    assert session_of(sessions, "zzz") is None
