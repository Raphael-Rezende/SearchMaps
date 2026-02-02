import { useEffect, useMemo, useState } from "react";
import styles from "../styles/Home.module.css";

const DEFAULT_LIMIT = 20;
const MAX_LIMIT = 50;

export default function Home() {
  const apiBase = useMemo(() => {
    return process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
  }, []);

  const [city, setCity] = useState("");
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(DEFAULT_LIMIT);
  const [jobId, setJobId] = useState("");
  const [status, setStatus] = useState(null);
  const [results, setResults] = useState([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");
  const [downloadUrl, setDownloadUrl] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isExporting, setIsExporting] = useState(false);

  useEffect(() => {
    if (!jobId) return;

    let isActive = true;
    const interval = setInterval(async () => {
      try {
        const response = await fetch(`${apiBase}/api/status/${jobId}`);
        if (!response.ok) {
          throw new Error("N?o foi poss?vel obter o status do job.");
        }

        const data = await response.json();
        if (!isActive) return;

        setStatus(data);

        if (["done", "error", "canceled"].includes(data.status)) {
          clearInterval(interval);
          setIsSubmitting(false);

          if (data.status === "done") {
            await fetchResults(jobId);
          }
        }
      } catch (err) {
        if (!isActive) return;
        setError(err.message || "Erro ao consultar status.");
        setIsSubmitting(false);
        clearInterval(interval);
      }
    }, 1500);

    return () => {
      isActive = false;
      clearInterval(interval);
    };
  }, [apiBase, jobId]);

  const fetchResults = async (currentJobId) => {
    try {
      const response = await fetch(`${apiBase}/api/results/${currentJobId}`);
      if (!response.ok) {
        throw new Error("N?o foi poss?vel obter os resultados.");
      }
      const data = await response.json();
      setResults(data.results || []);
      setTotal(data.total || 0);
    } catch (err) {
      setError(err.message || "Erro ao obter resultados.");
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");
    setDownloadUrl("");
    setResults([]);
    setTotal(0);

    if (!city.trim() || !query.trim()) {
      setError("Cidade e tipo de neg?cio s?o obrigat?rios.");
      return;
    }

    const safeLimit = Math.max(1, Math.min(Number(limit) || DEFAULT_LIMIT, MAX_LIMIT));
    setLimit(safeLimit);

    try {
      setIsSubmitting(true);
      const response = await fetch(`${apiBase}/api/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          city: city.trim(),
          query: query.trim(),
          limit: safeLimit,
        }),
      });

      if (!response.ok) {
        throw new Error("N?o foi poss?vel iniciar a busca.");
      }

      const data = await response.json();
      setJobId(data.jobId);
      setStatus({
        status: "queued",
        progress: 0,
        message: "Job criado. Aguardando execu??o...",
      });
    } catch (err) {
      setError(err.message || "Erro ao iniciar busca.");
      setIsSubmitting(false);
    }
  };

  const handleExport = async (format) => {
    if (!jobId) return;

    try {
      setIsExporting(true);
      const response = await fetch(`${apiBase}/api/export`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jobId, format }),
      });

      if (!response.ok) {
        const detail = await response.json();
        throw new Error(detail.detail || "Erro ao exportar arquivo.");
      }

      const data = await response.json();
      const url = data.downloadUrl.startsWith("http")
        ? data.downloadUrl
        : `${apiBase}${data.downloadUrl}`;

      setDownloadUrl(url);
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (err) {
      setError(err.message || "Erro ao exportar.");
    } finally {
      setIsExporting(false);
    }
  };

  const handleCancel = async () => {
    if (!jobId) return;
    try {
      await fetch(`${apiBase}/api/cancel/${jobId}`, { method: "POST" });
    } catch (err) {
      setError("N?o foi poss?vel cancelar o job.");
    }
  };

  const isRunning = status && ["queued", "running"].includes(status.status);
  const canExport = status && status.status === "done" && results.length > 0;

  return (
    <div className={styles.page}>
      <main className={styles.main}>
        <header className={styles.header}>
          <p className={styles.kicker}>SearchMaps DEMO</p>
          <h1>Busca de estabelecimentos no Google Maps</h1>
          <p className={styles.subtitle}>
            Demo p?blica sem banco de dados. Resultados ficam em mem?ria por job e voc?
            pode exportar em CSV ou Excel.
          </p>
        </header>

        <section className={styles.card}>
          <form className={styles.form} onSubmit={handleSubmit}>
            <div className={styles.field}>
              <label htmlFor="city">Cidade</label>
              <input
                id="city"
                type="text"
                placeholder="Ex: S?o Paulo, SP"
                value={city}
                onChange={(event) => setCity(event.target.value)}
                required
              />
            </div>

            <div className={styles.field}>
              <label htmlFor="query">Tipo de neg?cio</label>
              <input
                id="query"
                type="text"
                placeholder="Ex: pizzarias, cl?nicas, hot?is"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                required
              />
            </div>

            <div className={styles.field}>
              <label htmlFor="limit">Limite de resultados</label>
              <input
                id="limit"
                type="number"
                min={1}
                max={MAX_LIMIT}
                value={limit}
                onChange={(event) => setLimit(event.target.value)}
              />
              <span className={styles.helper}>M?ximo de {MAX_LIMIT} resultados por job.</span>
            </div>

            <div className={styles.actions}>
              <button type="submit" disabled={isSubmitting}>
                {isSubmitting ? "Buscando..." : "Iniciar busca"}
              </button>
              {isRunning && (
                <button type="button" className={styles.secondary} onClick={handleCancel}>
                  Cancelar
                </button>
              )}
            </div>
          </form>

          <div className={styles.status} aria-live="polite">
            <div>
              <strong>Status:</strong> {status?.message || "Aguardando..."}
            </div>
            <div className={styles.progressBar} aria-hidden="true">
              <span style={{ width: `${status?.progress || 0}%` }} />
            </div>
            {status?.error && <p className={styles.error}>{status.error}</p>}
            {error && <p className={styles.error}>{error}</p>}
          </div>
        </section>

        <section className={styles.results}>
          <div className={styles.resultsHeader}>
            <h2>Resultados</h2>
            <div className={styles.resultsMeta}>{total} encontrados</div>
          </div>

          {canExport && (
            <div className={styles.exportActions}>
              <button type="button" onClick={() => handleExport("csv")} disabled={isExporting}>
                Exportar CSV
              </button>
              <button
                type="button"
                onClick={() => handleExport("xlsx")}
                className={styles.secondary}
                disabled={isExporting}
              >
                Exportar Excel
              </button>
              {downloadUrl && (
                <a className={styles.download} href={downloadUrl}>
                  Baixar arquivo
                </a>
              )}
            </div>
          )}

          <div className={styles.tableWrapper}>
            <table>
              <thead>
                <tr>
                  <th>Nome</th>
                  <th>Endere?o</th>
                  <th>Telefone</th>
                  <th>Delivery</th>
                  <th>Website</th>
                </tr>
              </thead>
              <tbody>
                {results.length === 0 && (
                  <tr>
                    <td colSpan={5} className={styles.empty}>
                      Nenhum resultado para mostrar.
                    </td>
                  </tr>
                )}
                {results.map((item, index) => (
                  <tr key={`${item.name}-${index}`}>
                    <td>
                      {item.maps_url ? (
                        <a href={item.maps_url} target="_blank" rel="noreferrer">
                          {item.name}
                        </a>
                      ) : (
                        item.name
                      )}
                    </td>
                    <td>{item.address || "-"}</td>
                    <td>{item.phone || "-"}</td>
                    <td>{item.delivery || "-"}</td>
                    <td>
                      {item.website ? (
                        <a href={item.website} target="_blank" rel="noreferrer">
                          Site
                        </a>
                      ) : (
                        "-"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </div>
  );
}
