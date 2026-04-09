# Deploy: Streamlit Community Cloud + MotherDuck

## Pre-requisitos

- Conta em [motherduck.com](https://motherduck.com) (gratuita)
- Conta em [share.streamlit.io](https://share.streamlit.io) (gratuita, login com GitHub)
- Repositorio no GitHub (pode ser privado)
- Chaves de API: FRED, Alpha Vantage, Groq

## Passo 1 - Configurar o MotherDuck

1. Acesse [app.motherduck.com](https://app.motherduck.com) e crie uma conta
2. No painel, va em **Settings -> Tokens** e gere um token de servico
3. Guarde o token - voce vai usa-lo nos proximos passos
4. O banco `macro_pulse` sera criado automaticamente na primeira conexao

## Passo 2 - Popular o banco (seed inicial)

Execute localmente com suas chaves configuradas no `.env`:

```bash
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
# edite secrets.toml com seus valores reais

MOTHERDUCK_TOKEN=<seu_token> .\.venv\Scripts\python scripts/seed_motherduck.py
```

Isso carrega os dados historicos desde 2010. Leva alguns minutos.
Na primeira conexao, o DuckDB cria a pasta `.duckdb_home/` no repositorio para armazenar extensoes e cache local do MotherDuck. Ela ja esta ignorada no Git.

## Passo 3 - Subir o codigo no GitHub

```bash
git add .
git commit -m "feat: migrate to MotherDuck for cloud deploy"
git push origin main
```

Confirme que `.streamlit/secrets.toml` e `.env` **nao foram commitados**.

## Passo 4 - Criar o app no Streamlit Community Cloud

1. Acesse [share.streamlit.io](https://share.streamlit.io)
2. Clique em **New app**
3. Selecione seu repositorio e branch (`main`)
4. Defina o **Main file path** como `app.py`
5. Clique em **Advanced settings** -> **Secrets** e adicione:

```toml
MOTHERDUCK_TOKEN = "seu_token_aqui"
GROQ_API_KEY = "sua_chave_groq_aqui"
FRED_API_KEY = "sua_chave_fred_aqui"
ALPHA_VANTAGE_KEY = "sua_chave_alpha_vantage_aqui"
```

6. Clique em **Deploy**

## Passo 5 - Verificar o deploy

- O app ficara disponivel em `https://<seu-usuario>-macro-pulse.streamlit.app`
- Na primeira carga, o Streamlit instala as dependencias (~2 min)
- Se houver erros, verifique os logs em **Manage app -> Logs**

## Atualizacao de dados

O botao **"Atualizar dados"** no sidebar ja chama `load_all()`, que agora
escreve direto no MotherDuck. Qualquer usuario com acesso ao dashboard pode
disparar a atualizacao.

## Custos

| Servico | Plano gratuito |
|---|---|
| Streamlit Community Cloud | 1 app, 1 GB RAM, gratuito |
| MotherDuck | 10 GB storage, gratuito |
| FRED API | Ilimitado, gratuito |
| BCB API | Ilimitado, gratuito |
| Alpha Vantage | 25 req/dia, gratuito |
| Groq API | ~14.400 tokens/min, gratuito |

**Custo total: R$ 0,00**
