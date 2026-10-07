import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import type {
  AcademyArticle,
  AcademyCollection,
  EmployeeTrainingAssetAccessResponse,
} from "../api/contracts";
import { useSession } from "../session/SessionContext";

export function EmployeeAcademyPage() {
  const { slug } = useParams();
  const { client, status } = useSession();
  const [items, setItems] = useState<AcademyArticle[]>([]);
  const [article, setArticle] = useState<AcademyArticle | null>(null);
  const [cover, setCover] = useState<string | null>(null);
  const [coverError, setCoverError] = useState(false);
  const [offset, setOffset] = useState(0);
  const [next, setNext] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    if (status !== "authenticated") return;
    let active = true;
    // Попередню статтю приховуємо, поки сервер перевіряє нову адресу.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    setError(false);
    setArticle(null);
    setCover(null);
    setCoverError(false);
    const load = async () => {
      try {
        if (slug) {
          const detail = await client.request<AcademyArticle>(
            `/me/academy/${encodeURIComponent(slug)}`,
          );
          if (!active) return;
          setArticle(detail);
          if (detail.cover_asset_id) {
            try {
              const access = await client.request<EmployeeTrainingAssetAccessResponse>(
                `/me/academy/${encodeURIComponent(slug)}/cover`,
              );
              if (active) setCover(access.url);
            } catch {
              if (active) setCoverError(true);
            }
          }
        } else {
          const data = await client.request<AcademyCollection>(
            `/me/academy?offset=${offset}&limit=20`,
          );
          if (!active) return;
          setItems(data.items);
          setNext(data.next_offset);
        }
      } catch {
        if (active) setError(true);
      } finally {
        if (active) setLoading(false);
      }
    };
    void load();
    return () => {
      active = false;
    };
  }, [client, status, slug, offset, retry]);
  return (
    <section className="content-section academy-page">
      <p className="eyebrow">Додаткові матеріали</p>
      <h1>{article?.title_uk ?? "Академія"}</h1>
      <p>Необов’язкове читання. Статті не змінюють прогрес обов’язкового навчання.</p>
      {slug ? <Link to="/employee/academy">Усі статті</Link> : null}
      {loading ? (
        <p role="status">Завантаження…</p>
      ) : error ? (
        <div role="alert">
          <p>Стаття недоступна або не вдалося завантажити матеріали.</p>
          <button
            className="button button-secondary"
            onClick={() => setRetry((value) => value + 1)}
          >
            Спробувати ще раз
          </button>
        </div>
      ) : article ? (
        <article>
          <p>{article.summary_uk}</p>
          <p className="eyebrow">
            {article.category} · Оновлено {new Date(article.updated_at).toLocaleDateString("uk-UA")}
          </p>
          {cover && !coverError ? (
            <img className="academy-cover" src={cover} alt="" onError={() => setCoverError(true)} />
          ) : null}
          {coverError ? <p>Обкладинка тимчасово недоступна.</p> : null}
          {article.body_uk.split(/\n\s*\n/).map((paragraph, index) => (
            <p className="academy-paragraph" key={index}>
              {paragraph}
            </p>
          ))}
        </article>
      ) : (
        <>
          {items.length ? (
            items.map((item) => (
              <article className="training-panel" key={item.id}>
                <p className="eyebrow">{item.category}</p>
                <h2>
                  <Link to={`/employee/academy/${encodeURIComponent(item.slug)}`}>
                    {item.title_uk}
                  </Link>
                </h2>
                <p>{item.summary_uk}</p>
              </article>
            ))
          ) : (
            <p>Для вашої посади ще немає опублікованих статей.</p>
          )}
          <div className="compact-actions">
            {offset > 0 ? (
              <button
                className="button button-secondary"
                onClick={() => setOffset(Math.max(0, offset - 20))}
              >
                Попередні статті
              </button>
            ) : null}
            {next !== null ? (
              <button className="button button-secondary" onClick={() => setOffset(next)}>
                Наступні статті
              </button>
            ) : null}
          </div>
        </>
      )}
    </section>
  );
}
