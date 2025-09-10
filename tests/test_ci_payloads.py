import json


def test_comment_payload_structure():
    body = "See artifacts: tours/PR.md, maps/delta.svg"
    payload = {"content": {"raw": body}}
    assert json.dumps(payload)


def test_preset_script_builds_command(monkeypatch, tmp_path):
    import scripts.ci.preset_from_labels as p

    monkeypatch.setenv("UF_LABEL", "bug")
    rc = 0

    def fake_call(cmd, shell):
        assert "u lens preset bug" in cmd
        return 0

    monkeypatch.setattr(p.subprocess, "call", fake_call)
    rc = p.main()
    assert rc == 0
