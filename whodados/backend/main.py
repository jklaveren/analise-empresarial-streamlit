# NOME: main.py — FastAPI Entry Point
# LOCAL: whodados/backend/main.py
# Executa local: cd whodados/backend && uvicorn main:app --reload
# Build no Render: uvicorn main:app --host 0.0.0.0 --port $PORT
# =================================================================
import os
import sys
from pathlib import Path

# Garante que a raiz do projeto (contém auth_service, engine_dados, etc.)
# está no sys.path. Este arquivo está em whodados/backend/, então
# parents[1] = whodados/ e parents[2] = raiz do repo (onde fica o
# módulo `analise-empresarial-streamlit/` que contém o código legacy
# reutilizado: auth_service, engine_dados, database_config).
_raiz = Path(__file__).resolve().parents[2]
_raiz_alternativo = _raiz / "analise-empresarial-streamlit"
for _caminho in (_raiz, _raiz_alternativo):
    if _caminho.exists() and str(_caminho) not in sys.path:
        sys.path.insert(0, str(_caminho))

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from auth_service import autenticar_usuario, criar_access_token, decodificar_access_token
from database_config import ensure_app_tables
from engine_dados import _carregar_base_principal_impl

from backend.endpoints import router as endpoints_router

app = FastAPI(title="WhoDados API", version="1.0.0")
app.include_router(endpoints_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ensure_app_tables()


def get_current_user(authorization: str = None) -> dict:
    """Extrai e valida o token Bearer do header Authorization."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token não fornecido")
    token = authorization[7:]
    payload = decodificar_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado")
    return payload


# -------- Health --------
@app.get("/health")
def health():
    return {"status": "ok"}


# -------- Auth --------
class LoginRequest(BaseModel):
    username: str
    password: str


@app.post("/auth/login")
def auth_login(body: LoginRequest):
    user = autenticar_usuario(body.username, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    token = criar_access_token(user)
    return {"access_token": token, "token_type": "bearer"}
