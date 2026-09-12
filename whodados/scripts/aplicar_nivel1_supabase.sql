-- =================================================================
-- Aplica o "Nivel 1" de otimizacao de dados_empresas / dados_socios
-- DIRETO no banco atual, sem precisar rodar o pipeline inteiro.
--
-- O que faz:
--   1. Converte colunas monetarias de TEXT para NUMERIC(18,2)
--   2. Converte DATA_FUNDACAO de TEXT ('YYYYMMDD') para DATE
--   3. Fixa tamanhos dos codigos (CHAR(8), CHAR(14), CHAR(2), ...)
--   4. Dropa CONTATO_FONE e PORTE_NOME (redundantes; backend deriva no SELECT)
--   5. Faz VACUUM FULL para o espaco fisico ser realmente devolvido ao SO
--
-- Como rodar no Supabase:
--   Dashboard -> SQL Editor -> New query -> cola tudo -> Run.
--   Duracao esperada: 2-8 minutos (VACUUM FULL bloqueia leitura na tabela).
--
-- LOCAL: whodados/scripts/aplicar_nivel1_supabase.sql
-- =================================================================

-- Roda cada passo em transacao propria: se um cast falhar num valor
-- inesperado, so aquele passo aborta, os anteriores ficam. Ideal e todos
-- passarem; se algum quebrar, o log diz qual e a gente ajusta.

-- ----------------------------------------------------------------
-- 1. Dropa colunas redundantes
-- ----------------------------------------------------------------
BEGIN;
ALTER TABLE dados_empresas DROP COLUMN IF EXISTS "CONTATO_FONE";
ALTER TABLE dados_empresas DROP COLUMN IF EXISTS "PORTE_NOME";
COMMIT;

-- ----------------------------------------------------------------
-- 2. Colunas monetarias TEXT -> NUMERIC(18,2)
-- ----------------------------------------------------------------
-- NULLIF trata string vazia como NULL. REPLACE(',','.') cobre valores
-- gravados com virgula como separador decimal (formato pt-BR original
-- do CSV da Receita, antes do numeric cast).
-- Se a coluna ja for numerica (ex: rodou sync_dividas_only.py), o cast
-- e no-op.
BEGIN;
ALTER TABLE dados_empresas
  ALTER COLUMN "CAPITAL_SOCIAL"
    TYPE NUMERIC(18,2)
    USING NULLIF(REPLACE("CAPITAL_SOCIAL"::text, ',', '.'), '')::numeric;
COMMIT;

BEGIN;
ALTER TABLE dados_empresas
  ALTER COLUMN "DIVIDA_FEDERAL"
    TYPE NUMERIC(18,2)
    USING NULLIF(REPLACE("DIVIDA_FEDERAL"::text, ',', '.'), '')::numeric;
COMMIT;

BEGIN;
ALTER TABLE dados_empresas
  ALTER COLUMN "DIVIDA_PREVIDENCIARIA"
    TYPE NUMERIC(18,2)
    USING NULLIF(REPLACE("DIVIDA_PREVIDENCIARIA"::text, ',', '.'), '')::numeric;
COMMIT;

BEGIN;
ALTER TABLE dados_empresas
  ALTER COLUMN "DIVIDA_FGTS"
    TYPE NUMERIC(18,2)
    USING NULLIF(REPLACE("DIVIDA_FGTS"::text, ',', '.'), '')::numeric;
COMMIT;

BEGIN;
ALTER TABLE dados_empresas
  ALTER COLUMN "DIVIDA_TOTAL"
    TYPE NUMERIC(18,2)
    USING NULLIF(REPLACE("DIVIDA_TOTAL"::text, ',', '.'), '')::numeric;
COMMIT;

-- ----------------------------------------------------------------
-- 3. DATA_FUNDACAO TEXT('YYYYMMDD') -> DATE
-- ----------------------------------------------------------------
-- CASE trata os dois casos ruins: string vazia -> NULL; '00000000' ou
-- outros formatos que o to_date nao entende -> NULL (nao explode).
BEGIN;
ALTER TABLE dados_empresas
  ALTER COLUMN "DATA_FUNDACAO"
    TYPE DATE
    USING CASE
      WHEN "DATA_FUNDACAO"::text ~ '^[0-9]{8}$'
           AND "DATA_FUNDACAO"::text NOT LIKE '0000%'
        THEN to_date("DATA_FUNDACAO"::text, 'YYYYMMDD')
      ELSE NULL
    END;
COMMIT;

-- ----------------------------------------------------------------
-- 4. Codigos com tamanho fixo (CHAR/VARCHAR limitado)
-- ----------------------------------------------------------------
-- Ganha validacao (nao aceita string monstro por bug) e um bocado de
-- espaco em indices. Se o valor atual for maior que o CHAR(N), o cast
-- falha -- assinala que ha lixo no dado.
BEGIN;
ALTER TABLE dados_empresas
  ALTER COLUMN "CNPJ_BASICO" TYPE CHAR(8),
  ALTER COLUMN "CNPJ_COMPLETO" TYPE CHAR(14),
  ALTER COLUMN "PORTE_EMPRESA" TYPE CHAR(2);
COMMIT;

BEGIN;
ALTER TABLE dados_socios
  ALTER COLUMN "CNPJ_BASICO" TYPE CHAR(8),
  ALTER COLUMN "IDENTIFICADOR_SOCIO" TYPE CHAR(1);
COMMIT;

-- ----------------------------------------------------------------
-- 5. VACUUM FULL: devolve o espaco fisico ao sistema operacional
-- ----------------------------------------------------------------
-- Sem isso, o Postgres so marca as tuplas velhas como "livres" mas
-- nao encolhe o arquivo em disco. VACUUM FULL reescreve a tabela do
-- zero -- bloqueia leitura durante a execucao (~1-5 min por tabela
-- em 700k linhas).
--
-- Precisa rodar FORA de transacao. Se estiver no SQL Editor do Supabase,
-- roda cada linha separadamente ou marca a caixinha "no transaction".
VACUUM FULL dados_empresas;
VACUUM FULL dados_socios;

-- ----------------------------------------------------------------
-- 6. Confere o resultado
-- ----------------------------------------------------------------
-- Rodar depois pra ver o tamanho novo de cada tabela + indices.
SELECT
  schemaname,
  relname AS tabela,
  pg_size_pretty(pg_total_relation_size(relid)) AS total,
  pg_size_pretty(pg_relation_size(relid)) AS so_heap,
  pg_size_pretty(pg_indexes_size(relid)) AS so_indices
FROM pg_catalog.pg_statio_user_tables
WHERE relname IN ('dados_empresas', 'dados_socios', 'municipios', 'cnaes')
ORDER BY pg_total_relation_size(relid) DESC;
