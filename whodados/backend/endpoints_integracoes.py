"""
Endpoints de integração com serviços externos (Twilio WhatsApp, Brevo Email).
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime, timezone
from .auth import get_current_user
from .services.whatsapp_service import enviar_whatsapp, validar_whatsapp, get_twilio_auth_token
from .db.config import get_cur
from .db import registrar_mensagem_whatsapp, listar_conversas_whatsapp, listar_mensagens_whatsapp
from .logger import get_logger

log = get_logger(__name__)

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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falha ao enviar WhatsApp: {str(e)}")

    registrar_mensagem_whatsapp(
        telefone=telefone, direcao="saida", corpo=body, cnpj=cnpj,
        status="enviada", twilio_sid=result.get("sid"),
    )
    return result


@router.get("/whatsapp/conversas")
def api_listar_conversas_whatsapp(current_user: dict = Depends(get_current_user)):
    """Caixa de entrada: uma linha por numero, com a ultima mensagem e o
    total de nao lidas. Ordenado pela conversa mais recente primeiro."""
    return listar_conversas_whatsapp()


@router.get("/whatsapp/conversas/{telefone}")
def api_listar_mensagens_whatsapp(telefone: str, current_user: dict = Depends(get_current_user)):
    """Historico de uma conversa (mais antiga -> mais recente). Marca as
    mensagens recebidas como lidas ao abrir."""
    return listar_mensagens_whatsapp(telefone)


@router.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request):
    """Callback publico que o Twilio chama quando alguem manda uma mensagem
    de WhatsApp pro nosso numero. NAO tem autenticacao JWT (o Twilio nao
    manda nosso token) -- a seguranca aqui e' a assinatura X-Twilio-Signature,
    validada com o Auth Token. Sem Auth Token configurado, rejeita por
    seguranca (nunca aceita callback nao-assinado silenciosamente)."""
    form = await request.form()
    params = {k: v for k, v in form.items()}

    auth_token = get_twilio_auth_token()
    if not auth_token:
        log.warning("Webhook do WhatsApp chamado mas Twilio nao esta configurado -- ignorado.")
        raise HTTPException(status_code=503, detail="Integracao com Twilio nao configurada")

    from twilio.request_validator import RequestValidator
    validator = RequestValidator(auth_token)
    assinatura = request.headers.get("X-Twilio-Signature", "")
    # Atras de proxy (Render), request.url pode vir com scheme=http mesmo a
    # chamada real do Twilio tendo sido https -- usa X-Forwarded-Proto quando
    # presente pra reconstruir a URL exata que o Twilio assinou.
    url = str(request.url)
    proto_forwardado = request.headers.get("x-forwarded-proto")
    if proto_forwardado and url.startswith("http://"):
        url = proto_forwardado + url[len("http:"):]
    if not validator.validate(url, params, assinatura):
        log.warning("Assinatura Twilio invalida no webhook do WhatsApp -- requisicao rejeitada.")
        raise HTTPException(status_code=403, detail="Assinatura invalida")

    telefone = (params.get("From") or "").replace("whatsapp:", "")
    corpo = params.get("Body", "")
    sid = params.get("MessageSid", "")
    if telefone:
        registrar_mensagem_whatsapp(telefone=telefone, direcao="entrada", corpo=corpo, status="recebida", twilio_sid=sid)

    return Response(content="<Response></Response>", media_type="application/xml")