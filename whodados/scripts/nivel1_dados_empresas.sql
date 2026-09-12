-- =================================================================
-- Nivel 1 aplicado direto na tabela dados_empresas
--
-- Estrategia:
--   Um UNICO ALTER TABLE agrupa TODOS os DROP COLUMN + ALTER COLUMN
--   TYPE. Assim o Postgres reescreve o heap uma unica vez -- o rewrite
--   ja compacta a tabela (sem tuplas mortas, sem colunas removidas,
--   sem folgas). Nao precisa de VACUUM FULL depois, ganha ~10x em
--   tempo comparado a rodar ALTER por ALTER com VACUUM no fim.
--
-- Bloqueio:
--   O ALTER TABLE toma AccessExclusiveLock na dados_empresas durante
--   todo o rewrite (esperado: ~1-3 min pra ~700k linhas em plano
--   basico do Supabase). Queries do backend nessa tabela ficam em
--   espera; o backend ja tem fallback pra tabela ausente / queries
--   que falham (retorna [] ou {}), entao a UI segue funcionando.
--
-- Uso: Supabase Dashboard -> SQL Editor -> New query -> cola tudo -> Run.
-- =================================================================

-- ----------------------------------------------------------------
-- O ALTER unico: drops + type changes numa reescrita so
-- ----------------------------------------------------------------
-- Cada USING trata os valores feios inline (NULLIF pra '', regex pra
-- YYYYMMDD invalido) -- entao nao precisa UPDATE de limpeza antes.
ALTER TABLE dados_empresas
    DROP COLUMN IF EXISTS "CONTATO_FONE",
    DROP COLUMN IF EXISTS "PORTE_NOME",

    ALTER COLUMN "CAPITAL_SOCIAL"        TYPE NUMERIC(18,2)
        USING NULLIF(REPLACE("CAPITAL_SOCIAL"::text, ',', '.'), '')::numeric,
    ALTER COLUMN "DIVIDA_FEDERAL"        TYPE NUMERIC(18,2)
        USING NULLIF(REPLACE("DIVIDA_FEDERAL"::text, ',', '.'), '')::numeric,
    ALTER COLUMN "DIVIDA_PREVIDENCIARIA" TYPE NUMERIC(18,2)
        USING NULLIF(REPLACE("DIVIDA_PREVIDENCIARIA"::text, ',', '.'), '')::numeric,
    ALTER COLUMN "DIVIDA_FGTS"           TYPE NUMERIC(18,2)
        USING NULLIF(REPLACE("DIVIDA_FGTS"::text, ',', '.'), '')::numeric,
    ALTER COLUMN "DIVIDA_TOTAL"          TYPE NUMERIC(18,2)
        USING NULLIF(REPLACE("DIVIDA_TOTAL"::text, ',', '.'), '')::numeric,

    ALTER COLUMN "DATA_FUNDACAO"         TYPE DATE
        USING CASE
            WHEN "DATA_FUNDACAO"::text ~ '^[0-9]{8}$'
                 AND "DATA_FUNDACAO"::text NOT LIKE '0000%'
              THEN to_date("DATA_FUNDACAO"::text, 'YYYYMMDD')
            ELSE NULL
        END,

    ALTER COLUMN "CNPJ_BASICO"    TYPE CHAR(8),
    ALTER COLUMN "CNPJ_COMPLETO"  TYPE CHAR(14),
    ALTER COLUMN "PORTE_EMPRESA"  TYPE CHAR(2);

-- ----------------------------------------------------------------
-- Confere o resultado (tamanho + tipos)
-- ----------------------------------------------------------------
SELECT
  pg_size_pretty(pg_total_relation_size('dados_empresas')) AS total,
  pg_size_pretty(pg_relation_size('dados_empresas')) AS heap,
  pg_size_pretty(pg_indexes_size('dados_empresas')) AS indices;

SELECT column_name, data_type, character_maximum_length
FROM information_schema.columns
WHERE table_name = 'dados_empresas'
ORDER BY ordinal_position;
