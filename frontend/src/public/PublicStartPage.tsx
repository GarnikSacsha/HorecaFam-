import { Link } from "react-router-dom";

import logo from "../assets/bacara/bacara-logo.svg";
import bakery from "../assets/bacara/bakery.jpg";
import food from "../assets/bacara/food.jpg";
import team from "../assets/bacara/team.jpg";
import together from "../assets/bacara/together.jpg";
import { useSession } from "../session/SessionContext";
import { HomeRedirect } from "../session/SessionGate";
import "./bacara.css";

const resources = [
  {
    number: "01",
    title: "Меню в деталях",
    text: "Склад, подача й алергени. Знання, до яких можна повернутися перед розмовою з гостем.",
  },
  {
    number: "02",
    title: "Навчання по суті",
    text: "Короткі уроки та матеріали, призначені для твоєї роботи. Читай, розбирайся й повторюй у своєму темпі.",
  },
  {
    number: "03",
    title: "Практика та впевненість",
    text: "Закріплюй вивчене, перевіряй знання й переглядай власні результати. Крок за кроком.",
  },
];

export function BacaraLogo() {
  return <img className="bacara-logo" src={logo} width="903" height="555" alt="Bacara Coffee" />;
}

export function PublicStartPage() {
  const { status, session } = useSession();
  // Публічна історія не залежить від доступності API; підтверджена сесія зберігає свій маршрут.
  if (status === "authenticated" && session) return <HomeRedirect />;

  return (
    <div className="bacara-public">
      <a className="bacara-skip" href="#main-content">
        До основного вмісту
      </a>
      <header className="bacara-header bacara-container">
        <BacaraLogo />
        <nav className="bacara-navigation" aria-label="Навігація головної сторінки">
          <a href="#resources">Ресурси</a>
          <a href="#for-whom">Для кого</a>
        </nav>
        <Link className="bacara-login-link" to="/login">
          Увійти <span aria-hidden="true">↗</span>
        </Link>
      </header>

      <main id="main-content" tabIndex={-1} aria-label="Bacara Coffee — HoReCaFam">
        <section className="bacara-hero bacara-container" aria-labelledby="welcome-title">
          <div className="bacara-hero-copy">
            <p className="bacara-kicker">
              <span className="bacara-dot" aria-hidden="true" /> Простір команди Bacara
            </p>
            <h1 id="welcome-title">
              Гостинність починається <span>з тебе.</span>
            </h1>
            <p className="bacara-lead">
              За кожною чашкою — люди.
              <br />
              За впевненим сервісом — знання.
            </p>
            <p className="bacara-hero-note">
              Знайомся з Bacara, вивчай меню та зростай разом із командою. Твій простір навчання —
              тут.
            </p>
            <div className="bacara-hero-foot">
              <span>Кава. Люди. Гостинність.</span>
              <span aria-hidden="true">↓</span>
            </div>
          </div>
          <figure className="bacara-hero-figure">
            <img
              src={team}
              width="479"
              height="599"
              fetchPriority="high"
              alt="Команда Bacara разом на терасі кав’ярні"
            />
            <figcaption>
              <span>Люди, які створюють Bacara</span>
              <span aria-hidden="true">↗</span>
            </figcaption>
          </figure>
        </section>

        <section className="bacara-story bacara-container" aria-labelledby="story-title">
          <p className="bacara-kicker">Що таке Bacara</p>
          <div className="bacara-section-heading">
            <h2 id="story-title">
              Більше, ніж
              <br />
              зустріч за кавою.
            </h2>
            <p>
              Кава, гастрономія, атмосфера й люди поруч. Тут починається знайомство з Bacara — і з
              тим, як твоя робота стає частиною досвіду гостя.
            </p>
          </div>
          <div className="bacara-photo-pair">
            <figure>
              <div className="bacara-photo-frame bacara-food-frame">
                <img
                  src={food}
                  width="479"
                  height="599"
                  loading="lazy"
                  alt="Боул із овочами та інші страви меню Bacara"
                />
              </div>
              <figcaption>
                <span>01 / Гастрономія</span>
                <span>Знати, що рекомендуєш.</span>
              </figcaption>
            </figure>
            <figure>
              <div className="bacara-photo-frame bacara-bakery-frame">
                <img
                  src={bakery}
                  width="449"
                  height="598"
                  loading="lazy"
                  alt="Випічка Bacara в руках працівниці"
                />
              </div>
              <figcaption>
                <span>02 / Щоденні деталі</span>
                <span>Помічати те, що важливо.</span>
              </figcaption>
            </figure>
          </div>
          <div className="bacara-values">
            <article>
              <h3>Кава</h3>
              <p>Розуміти напій, щоб допомогти гостю знайти свій смак.</p>
            </article>
            <article>
              <h3>Гастрономія</h3>
              <p>Знати склад, подачу й алергени. Відповідати уважно та по суті.</p>
            </article>
            <article>
              <h3>Гостинність</h3>
              <p>Слухати, помічати й дбати. Саме з деталей складається враження.</p>
            </article>
          </div>
        </section>

        <section id="resources" className="bacara-resources" aria-labelledby="resources-title">
          <div className="bacara-container bacara-resources-grid">
            <div>
              <p className="bacara-kicker">Ресурси</p>
              <h2 id="resources-title">
                Знати більше.
                <br />
                Дбати краще.
              </h2>
              <p className="bacara-section-note">
                HoReCaFam збирає навчальні матеріали в одному просторі. Щоб потрібне знання було під
                рукою.
              </p>
            </div>
            <ol className="bacara-resource-list">
              {resources.map(({ number, title, text }) => (
                <li key={number}>
                  <span className="bacara-resource-number" aria-hidden="true">
                    {number}
                  </span>
                  <div>
                    <h3>{title}</h3>
                    <p>{text}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section
          id="for-whom"
          className="bacara-audience bacara-container"
          aria-labelledby="audience-title"
        >
          <p className="bacara-kicker">Для кого</p>
          <div className="bacara-section-heading">
            <h2 id="audience-title">
              Одна команда.
              <br />
              Спільна мова.
            </h2>
            <p>Для тих, хто щодня поруч із гостем, і тих, хто допомагає команді зростати.</p>
          </div>
          <div className="bacara-audience-grid">
            <article>
              <p className="bacara-kicker">У залі</p>
              <h3>Офіціантам і ранерам</h3>
              <p>
                Вивчай меню, проходь призначене навчання та повертайся до матеріалів. Знання
                допомагають почуватися впевненіше в роботі.
              </p>
            </article>
            <article>
              <p className="bacara-kicker">Поруч із командою</p>
              <h3>Адміністраторам</h3>
              <p>
                Готуй матеріали, призначай навчання та переглядай результати. Помічай, де потрібні
                пояснення й підтримка.
              </p>
            </article>
          </div>
        </section>

        <section className="bacara-team bacara-container" aria-labelledby="team-title">
          <figure>
            <img
              src={together}
              width="599"
              height="599"
              loading="lazy"
              alt="Команда Bacara святкує разом у закладі"
            />
            <figcaption>Bacara — це ми.</figcaption>
          </figure>
          <div>
            <p className="bacara-kicker">Твоя роль важлива</p>
            <h2 id="team-title">
              Гість запам’ятовує
              <br />
              не лише смак.
            </h2>
            <p>
              Він запам’ятовує, як його зустріли. Як допомогли обрати. Як відповіли на запитання.
            </p>
            <p>
              Твої знання й увага перетворюють звичайне замовлення на приємний досвід. Почнімо з
              того, що можемо вивчити сьогодні.
            </p>
          </div>
        </section>

        <section className="bacara-final" aria-labelledby="start-title">
          <div className="bacara-container">
            <p className="bacara-kicker">Bacara × HoReCaFam</p>
            <h2 id="start-title">
              Твій наступний крок —<br />
              знати трохи більше.
            </h2>
            <Link className="bacara-final-link" to="/login">
              Увійти до платформи <span aria-hidden="true">↗</span>
            </Link>
            <p className="bacara-access-note">Доступ для команди за запрошенням адміністратора.</p>
          </div>
        </section>
      </main>
      <footer className="bacara-footer bacara-container">
        <span>Bacara Coffee</span>
        <span>Простір навчання на HoReCaFam</span>
      </footer>
    </div>
  );
}
