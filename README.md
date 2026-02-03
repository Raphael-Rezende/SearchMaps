**Descrição**
SearchMaps é um minerador de dados do Google Maps em Python, usando Selenium (Chrome headless). Ele permite buscar estabelecimentos por cidade e tipo de negócio, exibir os resultados no terminal e exportar dados. Agora também inclui uma DEMO web com FastAPI + Next.js, focada em testes rápidos e sem uso de banco de dados.

**Modos de uso**
Terminal (FULL): usa SQLite para armazenar histórico local.
Web DEMO (stateless): resultados ficam em memória por job, sem SQLite.

**Execução local - Terminal (FULL)**
1. `cd Search`
2. `pip install selenium pandas xlsxwriter tabulate requests`
3. `python main.py`

**Execução local - API (DEMO)**
1. `cd api`
2. `python -m venv .venv`
3. `.venv\Scripts\activate`
4. `pip install -r requirements.txt`
5. `uvicorn main:app --reload --port 8000`

**Execução local - Web (DEMO)**
1. `cd web`
2. `npm install`
3. `npm run dev`

**Docker (API + Web juntos)**
1. `docker build -t searchmaps .`
2. `docker run --rm -p 3000:3000 searchmaps`
3. Acesse `http://localhost:3000`

**Configuração**
`web/.env.local`:
`NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`

Para Docker/Deploy com API + Web no mesmo dominio, use `NEXT_PUBLIC_API_BASE_URL=` (vazio).

**Configuração (FULL / Terminal)**
`SEARCHMAPS_MAX_LIMIT=200` (limite máximo por busca no modo local)
`SEARCHMAPS_SCROLL_MAX_TRIES=60`
`SEARCHMAPS_SCROLL_STALL_TRIES=8`
`SEARCHMAPS_BACKOFF_SECONDS=6`

**Exportações na DEMO**
Os arquivos CSV/XLSX são gerados em `./exports/` (na raiz do projeto).

**Observações importantes**
A versão DEMO não usa SQLite e não mantém histórico persistente. Se o servidor reiniciar, os jobs somem.
O limite padrão e máximo na DEMO é 10 resultados por job (configurável via SEARCHMAPS_DEMO_MAX_LIMIT).
Para evitar travar o servidor, há fila e rate limit por IP (SEARCHMAPS_MAX_QUEUE_JOBS e SEARCHMAPS_RATE_LIMIT_SECONDS).
Selenium/Chrome headless pode ter limitações em free-tier.

**Testes manuais (FULL)**
1. Execute o modo Terminal.
2. Use a busca com cidade `Belo Horizonte` e tipo `restaurantes`.
3. Defina `SEARCHMAPS_MAX_LIMIT=200` e rode a busca.
4. Esperado: logs da Fase A/Fase B e coleta até 200 itens (ou até o fim real da lista).

**Deploy sugerido**
Frontend: Vercel
Backend: Render, Railway ou Fly.io

**Deploy Docker (API + Web juntos)**
1. Suba o repositório no GitHub.
2. Crie um Web Service com build via Dockerfile.
3. Configure a porta exposta (PORT) para o Next (padrão 3000) e deixe `NEXT_PUBLIC_API_BASE_URL` vazio.
4. Deploy.

**Resumo**
Terminal = FULL (com SQLite)
Web = DEMO (stateless, sem banco)
