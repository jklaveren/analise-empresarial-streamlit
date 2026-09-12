"""
Endpoints de integração com serviços externos (Twilio WhatsApp, Brevo Email).
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime, timezone
from .auth import get_current_user
from .services.whatsapp_service import enviar_whatsapp, validar_whatsapp
from .db.config import get_cur

router = APIRouter(prefix="/api/v1/integracoes", tags=["Integrações"])


@router.get("")
def listar_integracoes(current_user: dict = Depends(get_current_user)):
    """
    Lista as integrações configuradas. Os valores são ofuscados na resposta
    (mostra somente o início) para não expor credenciais completas.
    """
    try:
        with get_cur() as cur:
            cur.execute(
                "SELECT id, key, value, descricao, ativo, updated_at "
                "FROM integracao_configs ORDER BY key"
            )
            linhas = cur.fetchall()
        resultado = []
        for r in linhas:
            valor = r["value"] or ""
            if valor:
                valor_mostrado = (
                    valor[:6] + "…" + valor[-4:] if len(valor) > 14 else "•••"
                )
            else:
                valor_mostrado = None
            resultado.append({
                "id": r["id"],
                "key": r["key"],
                "value": valor_mostrado,
                "descricao": r["descricao"],
                "ativo": r["ativo"],
                "configurado": bool(r["value"]),
            })
        return resultado
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao listar integrações: {str(e)}")


class IntegracaoIn(BaseModel):
    key: str
    value: str
    descricao: Optional[str] = None


@router.post("")
def salvar_integracao(payload: IntegracaoIn, current_user: dict = Depends(get_current_user)):
    """
    Salva/atualiza o valor de uma integração. Mantém o valor por extenso no
    banco (usado em runtime); quem chama envia o valor real.
    """
    chaves_permitidas = {"brevo_api_key", "twilio_sid", "twilio_token", "twilio_wa_number"}
    key = (payload.key or "").strip()
    if key not in chaves_permitidas:
        raise HTTPException(status_code=400, detail="Chave de integração não permitida.")
    valor = (payload.value or "").strip()
    if not valor:
        raise HTTPException(status_code=400, detail="Valor não pode ser vazio.")
    try:
        with get_cur() as cur:
            cur.execute(
                """INSERT INTO integracao_configs (key, value, descricao, ativo, created_at, updated_at)
                   VALUES (%s, %s, %s, TRUE, NOW(), NOW())
                   ON CONFLICT (key) DO UPDATE
                     SET value = EXCLUDED.value,
                         descricao = COALESCE(EXCLUDED.descricao, integracao_configs.descricao),
                         ativo = TRUE,
                         updated_at = NOW()
                 RETURNING id, key, descricao, ativo""",
                (key, valor, payload.descricao),
            )
            registro = cur.fetchone()
        return {"ok": True, "chave": key, "configurado": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao salvar integração: {str(e)}")


@router.post("/whatsapp/enviar")
async def api_enviar_whatsapp(payload: Dict, current_user: dict = Depends(get_current_user)):
    """
    Envia uma mensagem de WhatsApp para uma empresa.
    
    Body:
    {
      "cnpj": "12345678000195",
      "telefone": "+5551999999999",
      "mensagem": "Seu texto aqui (opcional)"
    }
    """
    telefone = payload.get("telefone")
    cnpj = payload.get("cnpj")
    mensagem = payload.get("mensagem")
    
    if not telefone:
        raise HTTPException(status_code=400, detail="Telefone é obrigatório")
    
    if not validar_whatsapp(telefone):
        raise HTTPException(status_code=400, detail="Formato de telefone inválido. Use +55XXXXXXXXXX")
    
    # Mensagem padrão se não for enviada
    body = mensagem or f"Olá! Esta é uma mensagem automática do WhoDados. Empresa CNPJ: {cnpj}"
    
    try:
        result = enviar_whatsapp(telefone, body)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falha ao enviar WhatsApp: {str(e)}")