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
