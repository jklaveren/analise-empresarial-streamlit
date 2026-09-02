"""
Endpoints /empresas e /crm — FastAPI.
LOCAL: whodados/backend/endpoints.py
Importado pelo main.py via `from backend.endpoints import router`
"""
import os
import sys
from pathlib import Path
from typing import Optional

# Adiciona raiz do repo ao sys.path para encontrar auth_service, engine_dados, etc.
_raiz = Path(__file__).resolve().parents[2]
_raiz_alternativo = _raiz / "analise-empresarial-streamlit"
for _caminho in (_raiz, _raiz_alternativo):
    if _caminho.exists() and str(_caminho) not in sys.path:
        sys.path.insert(0, str(_caminho))

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from engine_dados import _carregar_base_principal_impl
from auth_service import decodificar_access_token

router = APIRouter()


def get_current_user(authorization: str = None) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token não fornecido")
    token = authorization[7:]
    payload = decodificar_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado")
    return payload


def _carregar_socios_csv(cnpj: str, output_dir: str = None) -> list[dict]:
    if output_dir is None:
        # Resolve a partir da localização deste script (whodados/backend/)
        output_dir = str(Path(__file__).resolve().parents[1] / "pipeline" / "out")
    import pandas as pd
    socios_path = Path(output_dir) / "socios_rs.csv"
    if not socios_path.exists():
        return []
    df = pd.read_csv(socios_path, dtype=str, sep=";", low_memory=False)
    if "cnpj_completo" not in df.columns:
        return []
    df = df[df["cnpj_completo"] == cnpj].fillna("")
    cols = [c for c in ["nome_socio", "cpf_cnpj_socio", "qualif_socio"] if c in df.columns]
    return df[cols].to_dict(orient="records")


def _carregar_crm(cnpj: str) -> dict | None:
    import psycopg2
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        return None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute(
            "SELECT status, notas, data_atualizacao FROM crm WHERE cnpj = %s LIMIT 1",
            (cnpj,),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            return {
                "status": row[0] or "",
                "notas": row[1] or "",
                "data_atualizacao": str(row[2]) if row[2] else None,
            }
    except Exception:
        pass
    return None


@router.get("/empresas")
def listar_empresas(
    cidade: Optional[str] = None,
    cnae: Optional[str] = None,
    busca: Optional[str] = None,
    user: dict = Depends(lambda authorization=None: get_current_user(authorization)),
):
    try:
        _, df = _carregar_base_principal_impl()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao carregar base: {e}")

    if cidade:
        df = df[df["municipio"] == cidade]
    if cnae:
        df = df[df["cnae_principal"] == cnae]
    if busca:
        df = df[df["razao_social"].str.contains(busca, case=False, na=False)]

    cols = [
        "cnpj_completo", "razao_social", "nome_fantasia",
        "municipio", "cnae_principal", "capital_social",
        "divida_total", "porte_nome", "data_fundacao",
    ]
    available = [c for c in cols if c in df.columns]
    return df[available].fillna("").to_dict(orient="records")


@router.get("/empresas/{cnpj}")
def get_empresa(
    cnpj: str,
    user: dict = Depends(lambda authorization=None: get_current_user(authorization)),
):
    try:
        _, df = _carregar_base_principal_impl()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao carregar base: {e}")

    row = df[df["cnpj_completo"] == cnpj]
    if row.empty:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")

    empresa = row.iloc[0].to_dict()
    empresa["socios"] = _carregar_socios_csv(cnpj)
    empresa["crm"] = _carregar_crm(cnpj)
    return empresa


class CrmUpdate(BaseModel):
    status: Optional[str] = None
    notas: Optional[str] = None


@router.put("/crm/{cnpj}")
def atualizar_crm(
    cnpj: str,
    body: CrmUpdate,
    user: dict = Depends(lambda authorization=None: get_current_user(authorization)),
):
    import psycopg2
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL não configurado")

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO crm (cnpj, status, notas, data_atualizacao)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (cnpj) DO UPDATE SET
            status = COALESCE(EXCLUDED.status, crm.status),
            notas = COALESCE(EXCLUDED.notas, crm.notas),
            data_atualizacao = NOW()
    """, (cnpj, body.status, body.notas))
    conn.commit()
    cur.execute("SELECT status, notas, data_atualizacao FROM crm WHERE cnpj = %s", (cnpj,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return {"status": body.status, "notas": body.notas, "data_atualizacao": None}
    return {"status": row[0], "notas": row[1], "data_atualizacao": str(row[2]) if row[2] else None}
