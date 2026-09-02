"""
Tradução de pergunta em português -> FiltroEmpresas, via tool use da API
da Anthropic (o modelo é forçado a chamar a "ferramenta" filtrar_empresas
com argumentos que batem exatamente com o schema Pydantic — não existe
caminho para o modelo devolver texto livre nem SQL).

Variável de ambiente nova: ANTHROPIC_API_KEY (mesmo padrão de .env.example
que RF_SHARE_TOKEN e SMTP_* já seguem no projeto).
"""

from __future__ import annotations

import json
import os

import anthropic

from backend.app.nlp.schemas import FiltroEmpresas

_CLIENTE = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

_FERRAMENTA_FILTRO = {
    "name": "filtrar_empresas",
    "description": (
        "Filtra a base de empresas do RS de acordo com os critérios extraídos "
        "da pergunta do usuário. Só preencha os campos que a pergunta menciona "
        "de fato — não invente valores."
    ),
    "input_schema": FiltroEmpresas.model_json_schema(),
}

_SYSTEM_PROMPT = """Você traduz perguntas em português sobre empresas do RS
em filtros estruturados. Você NUNCA responde em texto livre e NUNCA escreve
SQL — sua única saída é uma chamada da ferramenta filtrar_empresas.

Exemplos:
- "empresas de comércio em Porto Alegre com dívida acima de 100 mil"
  -> cnae_prefixo="47", municipio="Porto Alegre", divida_min=100000
- "as 10 maiores empresas por capital social"
  -> ordenar_por="CAPITAL_SOCIAL", ordem="desc", limite=10

Se a pergunta não tiver relação com dados de empresas, preencha o filtro
mais neutro possível (sem cnae/município) e deixe o limite padrão."""


def interpretar_pergunta(pergunta: str) -> FiltroEmpresas:
    resposta = _CLIENTE.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        tools=[_FERRAMENTA_FILTRO],
        tool_choice={"type": "tool", "name": "filtrar_empresas"},
        messages=[{"role": "user", "content": pergunta}],
    )

    bloco_ferramenta = next(b for b in resposta.content if b.type == "tool_use")
    # FiltroEmpresas valida os campos aqui — qualquer coisa fora do schema
    # (tipo errado, enum inválido, cnae com letra) já derruba antes de
    # chegar perto de uma query real.
    return FiltroEmpresas.model_validate(bloco_ferramenta.input)


def resumir_resultado(pergunta: str, filtro: FiltroEmpresas, total: int) -> str:
    """Frase curta pro frontend mostrar acima da tabela de resultados.
    Não precisa de outra chamada de LLM — é só template, mantém custo e
    latência baixos para o caminho mais comum."""
    partes = [f"{total} empresa(s) encontrada(s)"]
    if filtro.municipio:
        partes.append(f"em {filtro.municipio}")
    if filtro.cnae_prefixo:
        partes.append(f"no setor CNAE {filtro.cnae_prefixo}")
    if filtro.divida_min:
        partes.append(f"com dívida a partir de R$ {filtro.divida_min:,.0f}")
    return " ".join(partes) + "."
