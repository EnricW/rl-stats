"""Tests de la inferencia de fases del visor (frames._phase_map)."""

from pipeline.frames import _phase_map


def _mf(t, state, tr=0):
    return {
        "time": t,
        "replicated_game_state_name": state,
        "replicated_game_state_time_remaining": tr,
    }


def test_phase_map_infiere_por_comportamiento():
    """Los índices de estado varían por replay: la cuenta atrás se reconoce
    por su time_remaining (3-2-1) y el gol por empezar en el instante del gol."""
    meta = [
        _mf(0.0, 73, 3), _mf(1.0, 73, 0),      # cuenta atrás inicial
        _mf(4.0, 74), _mf(10.0, 74),            # juego
        _mf(20.0, 95), _mf(22.0, 95),           # gol en t=20
        _mf(28.0, 98),                           # marcador suelto (fin de replay)
        _mf(28.1, 73, 3), _mf(31.0, 73, 0),     # cuenta atrás tras el gol
        _mf(32.0, 74),
    ]
    mapping = _phase_map(meta, goal_times=[20.0])
    assert mapping[73] == 0   # cuenta atrás
    assert mapping[74] == 1   # juego
    assert mapping[95] == 2   # gol/repetición
    assert mapping[98] == 1   # desconocido -> juego


def test_phase_map_enum_antiguo():
    """El replay de muestra de 2016 usaba 0/2/3: debe seguir funcionando."""
    meta = [
        _mf(0.0, 0, 3), _mf(2.0, 0, 0),
        _mf(4.0, 2), _mf(30.0, 2),
        _mf(50.0, 3), _mf(52.0, 3),
    ]
    mapping = _phase_map(meta, goal_times=[50.0])
    assert mapping == {0: 0, 2: 1, 3: 2}


def test_phase_map_sin_goles():
    mapping = _phase_map([_mf(0.0, 7, 3), _mf(3.0, 8)], goal_times=[])
    assert mapping == {7: 0, 8: 1}
