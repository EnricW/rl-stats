"""Tests del registro central (data/manifest.json): estado por etapa,
reintentos acotados, dedup por match_guid y registro de informes."""

import copy

import pipeline.manifest as mf


def _empty():
    return copy.deepcopy(mf._EMPTY)


def test_stage_pending_ciclo_completo(tmp_path, monkeypatch):
    monkeypatch.setattr(mf, "FRAMES_DIR", tmp_path)
    manifest = _empty()

    # nunca generado: toca
    assert mf.stage_pending(manifest, "r1", "frames", 1) is True

    # fallos: acumulan intentos hasta desistir
    for _ in range(mf.MAX_ATTEMPTS):
        st = mf.record_stage(manifest, "r1", "frames", 1, ok=False, error=RuntimeError("boom"))
    assert st["attempts"] == mf.MAX_ATTEMPTS
    assert st["error"] == "boom"
    assert mf.stage_pending(manifest, "r1", "frames", 1) is False  # desistido

    # una versión nueva del extractor vuelve a intentarlo (intentos a cero)
    assert mf.stage_pending(manifest, "r1", "frames", 2) is True
    st = mf.record_stage(manifest, "r1", "frames", 2, ok=False, error="otra vez")
    assert st["attempts"] == 1

    # éxito con salida en disco: al día
    (tmp_path / "r1.json").write_text("{}", encoding="utf-8")
    mf.record_stage(manifest, "r1", "frames", 2, ok=True)
    assert mf.stage_pending(manifest, "r1", "frames", 2) is False
    # subir la versión regenera aunque el archivo exista
    assert mf.stage_pending(manifest, "r1", "frames", 3) is True

    # salida borrada (p. ej. backfill): vuelve a tocar
    (tmp_path / "r1.json").unlink()
    assert mf.stage_pending(manifest, "r1", "frames", 2) is True


def test_register_report_sustituye_misma_fecha():
    manifest = _empty()
    mf.register_report(manifest, "2026-10-15", "reports/team-2026-10-15.md", "model-a")
    mf.register_report(manifest, "2026-10-15", "reports/team-2026-10-15.md", "model-b")
    assert len(manifest["reports"]["team"]) == 1
    assert manifest["reports"]["team"][0]["model"] == "model-b"

    mf.register_report(manifest, "2026-10-08", "reports/player-Enric-2026-10-08.md",
                       "model-a", name="Enric")
    mf.register_report(manifest, "2026-10-15", "reports/player-Enric-2026-10-15.md",
                       "model-a", name="Enric")
    dates = [i["date"] for i in manifest["reports"]["players"]["Enric"]]
    assert dates == ["2026-10-08", "2026-10-15"]  # orden ascendente estable


def test_known_guids_ignora_duplicados():
    manifest = _empty()
    manifest["matches"] = {
        "a": {"match_guid": "g1"},
        "b": {"match_guid": "g1", "duplicate_of": "a"},
        "c": {},  # sin guid (partida migrada): no participa en el dedup
    }
    assert mf.known_guids(manifest) == {"g1": "a"}


def test_register_player_report_dedup_por_sesion():
    manifest = _empty()
    mf.register_player_report(manifest, "Enric", "2026-10-14-1951", "2026-10-14",
                              13, "reports/player-Enric-2026-10-14-1951.md", "opus")
    # misma sesión regenerada: sustituye, no duplica
    mf.register_player_report(manifest, "Enric", "2026-10-14-1951", "2026-10-14",
                              13, "reports/player-Enric-2026-10-14-1951.md", "opus-2")
    items = manifest["reports"]["players"]["Enric"]
    assert len(items) == 1 and items[0]["model"] == "opus-2"

    # dos sesiones el MISMO día ya no se pisan (era el bug del nombre por fecha)
    mf.register_player_report(manifest, "Enric", "2026-10-14-2330", "2026-10-14",
                              4, "reports/player-Enric-2026-10-14-2330.md", "opus")
    items = manifest["reports"]["players"]["Enric"]
    assert [i["session_id"] for i in items] == ["2026-10-14-1951", "2026-10-14-2330"]
    assert [i["games"] for i in items] == [13, 4]


def test_migracion_v1_a_v2():
    v1 = {
        "schema_version": 1,
        "matches": {},
        "reports": {
            "team": [{"date": "2026-10-15", "path": "reports/team-2026-10-15.md",
                      "model": "opus"}],
            # items del esquema viejo: por ciclo de partidas, sin session_id
            "players": {"Enric": [{"date": "2026-10-15", "path": "x.md", "model": "opus"}]},
        },
        "player_reports_state": {"Enric": 28},
    }
    v2 = mf._migrate_v1_to_v2(v1)
    assert v2["schema_version"] == 2
    assert "player_reports_state" not in v2
    assert v2["reports"]["players"]["Enric"] == []   # descartado: no era sesión
    assert len(v2["reports"]["team"]) == 1           # el de equipo se conserva

    # idempotente: un manifiesto ya en v2 no se toca
    sin_cambios = mf._migrate_v1_to_v2(dict(v2))
    assert sin_cambios["reports"]["team"] == v2["reports"]["team"]
