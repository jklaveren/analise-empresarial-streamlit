"""Testes da dependencia get_active_org (empresa ativa + validacao de acesso)."""
import pytest
from fastapi import HTTPException
from backend.auth import dependencies as dep


def test_header_com_acesso(monkeypatch):
    monkeypatch.setattr("backend.db.service.usuario_tem_acesso_org", lambda u, o: True)
    assert dep.get_active_org({"sub": "jeh"}, x_org_id=2) == 2


def test_header_sem_acesso_bloqueia(monkeypatch):
    monkeypatch.setattr("backend.db.service.usuario_tem_acesso_org", lambda u, o: False)
    with pytest.raises(HTTPException) as exc:
        dep.get_active_org({"sub": "jeh"}, x_org_id=99)
    assert exc.value.status_code == 403


def test_sem_header_cai_na_primeira_empresa(monkeypatch):
    monkeypatch.setattr("backend.db.service.listar_organizacoes_do_usuario", lambda u: [{"id": 1}, {"id": 2}])
    assert dep.get_active_org({"sub": "jeh"}, x_org_id=None) == 1


def test_sem_empresa_bloqueia(monkeypatch):
    monkeypatch.setattr("backend.db.service.listar_organizacoes_do_usuario", lambda u: [])
    with pytest.raises(HTTPException) as exc:
        dep.get_active_org({"sub": "jeh"}, x_org_id=None)
    assert exc.value.status_code == 403
