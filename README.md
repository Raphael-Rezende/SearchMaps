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

**Configuração**
`web/.env.local`:
`NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`

**Exportações na DEMO**
Os arquivos CSV/XLSX são gerados em `./exports/` (na raiz do projeto).

**Observações importantes**
A versão DEMO não usa SQLite e não mantém histórico persistente. Se o servidor reiniciar, os jobs somem.
O limite padrão e máximo na DEMO é 10 resultados por job (configurável via SEARCHMAPS_DEMO_MAX_LIMIT).
Para evitar travar o servidor, há fila e rate limit por IP (SEARCHMAPS_MAX_QUEUE_JOBS e SEARCHMAPS_RATE_LIMIT_SECONDS).
Selenium/Chrome headless pode ter limitações em free-tier.

**Deploy sugerido**
Frontend: Vercel
Backend: Render, Railway ou Fly.io

**Resumo**
Terminal = FULL (com SQLite)
Web = DEMO (stateless, sem banco)
