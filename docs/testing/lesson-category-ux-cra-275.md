# CRA-275 — аудит і локальна структура уроків, 2026-09-23

## Подальша авторизація доставки

Після локального checkpoint Denys дозволив запис у Linear: comment
`ca175040-af90-4652-91b4-64992a389de5` збережено й перевірено повторним читанням.
Наступним прямим запитом авторизовано commit + push та autodeploy за наведеною нижче мапою.
Свіжий Railway read підтвердив відсутність GitHub source для API/web; доставка включає
підключення лише цих двох наявних staging services до main після перевіреного push,
зі збереженням build/runtime settings. Worker, cron, migration-runner і hosted Training
не змінюються. Старі записи про відсутність дозволів нижче описують попередній checkpoint.

## Результат

Локальний reader повертається до списку уроків свого модуля, зокрема після прямого відкриття
посилання та після завершення. Картки показують назву, категорію й короткий опис із точної
Menu-залежності призначеного Training. Заголовки другого рівня утворюють зміст із кількістю
карток; посилання переводить фокус до відповідного розділу. Відомі службові абзаци варіантів
знімка згорнуті через native details, звичайний навчальний текст залишається видимим.
Наявна модальна картка, retry, Escape і повернення фокусу збережені.

Підготовлено окрему локальну структуру всіх 308 позицій: 124 їжі, 40 десертів/морозива,
63 вина/коктейлів/інших позицій, 81 напій. Збережено чотири stable Lesson ID.
Основні категорії їжі: Стартери → Сніданкові сніданки → Хелсі-сніданки → Супи → Салати →
Млинці → Сендвічі та бургери → Боули → Щось особливе → Кідс меню → Додатки.
Це порядок наявного імпортного джерела, не алфавітне сортування.

**Hosted Training не змінено.** Виправлення складу уроків підготовлене як локальний review
packet наступної версії, а не застосоване до опублікованих блоків. Самої доставки reader
недостатньо, щоб прибрати старе морозиво з основного потоку вже опублікованого уроку.

## Аудит джерел і стану

- Новий worktree починався чистим, detached `4b45108`; це старіша база за доставлений продукт.
- Dirty main `4b45108` і `codex/cra-272-authored-final@7cffa59` перевірені окремо та не змінені.
- Глобальний harness знайдено на диску D; checkout SHA збігається з pin
  `3eaa9586b4e09e70399c2600aa1808b18449a15d`. Прочитані operating contract, router, profile,
  policies, workflows, security, code quality, project patterns; bootstrap не запускався.
- Прочитані локальні AGENTS, START-HERE, UPSTREAM, CODE-QUALITY, SECURITY, TESTING,
  GIT-WORKFLOW, backend/AGENTS, поточні STATUS/CONTEXT та близькі код/тести.
- Linear: START HERE, CRA-275 і всі його comments; пов'язані CRA-148/237/238/240/271/272/274/122;
  релевантні повні секції FINAL CRA-12 про typed blocks, assignment-bound reads,
  publication та rollout. Старі дати/дозволи не стали новою авторизацією.
- Перевірено SHA архіву CRA-275
  `adc1717bd07190431d3dd6080bd21358c46d3bc3d0c326580b36a52dba0d6ff3`: 420 файлів,
  усі 420 hashes збігаються, зайвих entries немає. Архів не змінювався.
- Цей точний пакет перенесений у чистий worktree як успадкована база. Відносно HEAD він
  містить 55 змістовно відмінних/нових шляхів. Вони **не є 55 новими UX-правками**.
  Окремий `outputs/lesson-ux/inherited-paths.json` фіксує їх; baseline-manifest.json
  зберігає hashes. Власний UX diff відносно доставки містить дев'ять шляхів нижче.
- Свіжа authenticated read-only Chrome перевірка staging підтвердила призначену версію 2,
  4/4 завершені уроки, старі однакові кнопки/variant paragraphs у Food, повернення на root
  і наявну історію lesson test 5/5. Attempts/completions не створювалися.
- Shell HTTP probe отримав локальний connection refusal; браузер staging відкриває.
  Новий provider deployment inventory і повний HTTP smoke цієї сесії не заявляються.

| Напрям | Підтверджений стан | Що залишається |
| --- | --- | --- |
| CRA-271 | Done у Linear, доставлена поведінка входить до перевіреного пакета | Не повторювати доставку/публікацію |
| CRA-237/238/240 | In Progress у Linear; історичні commits/delivery у джерелах | Окреме приймання, статус не змінювати автоматично |
| CRA-272/274 | In Progress; код authored Final/cycles і migration 0021 у пакеті | Приймання відокремлене від доставки; старе «не deployed» застаріло |
| CRA-275 | Доставка записана останнім comment; UX feedback залишається відкритим | Поточні локальні зміни й наступний content gate |
| CRA-148 | 308-item source пакет існує; підготовка не дорівнює підтвердженим фактам | Venue confirmation та наступний Training review |
| CRA-122 | In Progress | Worker/cron/provider, ширше staging/pilot acceptance не доведені цим проходом |

Опис CRA-275 та останній CRA-274 pointer у START HERE відстають від пізнішого delivery comment.
Це розбіжність обліку виконання, а не дозвіл повторити операцію. Історичні 979 backend та
147 frontend / 84 browser checks попередніх delivery залишаються історичними числами.
Цей аудит не є новим repository-wide security scan або повним backend coverage run.

## Обмежений scope та ordered commit map

Прямий запит Denys авторизує локальну реалізацію UX. Створення окремої Linear issue було
відхилено через free issue limit. Запис scope/evidence до наявної CRA-275 автоматичний
approval review відхилив через вимогу прямого дозволу на повідомлення; підтвердження запитано.
Жодного успішного Linear write у цьому кроці немає. Локальний scope залишається follow-up CRA-275.

Мапа визначена до реалізації; Git index не змінюється, commits не дозволені:

1. `chore: reconcile delivered lesson baseline`: точні 420 source entries, 55 inherited paths;
   hash-перевірка, без змін інших worktrees. Це окрема майбутня baseline boundary.
2. `feat(training): expose scoped lesson reading context`: schemas/training.py,
   services/employee_training.py, services/employee_menu.py,
   tests/api/test_lesson_reading_context.py; API types у contracts.ts.
   Використано existing Menu summary/query замість дублювання SQL в новому модулі.
   RED/GREEN на real test PostgreSQL, retained dependency, access regression, Ruff/mypy.
3. `feat(training): organize lesson reading and contextual return`:
   EmployeeLearningLessonPage.tsx, EmployeeLessonStructure.test.tsx,
   e2e/lesson-structure.spec.ts, styles.css. RED/GREEN, overlay regression, responsive/focus,
   types/lint/format/build. Типи shared contracts відносяться до межі 2.
4. `docs: record lesson UX and content rollout preparation`: цей звіт, STATUS.md.
   Документаційний TDD exception: source/diff/link/inventory review. Customer packet,
   screenshots, helpers та patch/manifests під outputs залишаються локальними й не staging.

Власні production paths: backend/app/schemas/training.py;
backend/app/services/employee_menu.py; backend/app/services/employee_training.py;
frontend/src/api/contracts.ts; frontend/src/employee/EmployeeLearningLessonPage.tsx;
frontend/src/styles.css. Три нові test paths перелічені в мапі.
Для selective staging спершу потрібна окрема authorisation та розділення inherited baseline
від дев'яти UX paths; staging цілих shared файлів із HEAD змішав би різні виконані задачі.

## Контракт та review

Additive GET response: EmployeeTrainingLessonDetail.module_id — stable Module UUID;
EmployeeTrainingContentBlock.menu_item — nullable EmployeeMenuItemSummary.
Write payload typed blocks незмінений. Дані вибираються лише після перевірки власного
non-revoked assignment/lesson, за TrainingVersionMenuDependency; не за current Menu.
Читання не створює progress, source-note provenance чи answer keys не додаються.
Frontend зберігає fallback для старої відповіді без metadata; URL segment кодується.
Додаткова робота на урок — dependency lookup, один bulk Menu query та Module lookup,
а не HTTP-запит для кожної картки. Dependencies/endpoints/schema migrations не додані.

Окремий свіжий review bounded diff перевірив scope resolution, retained-version query,
safe response projection, escaped React text, відсутність writes, фокус/якорі, fallback
і збереження модальної поведінки. У межах цього diff Critical/High не знайдено.
Наявна модалка продовжує показувати current Menu через чинний endpoint; inline preview
показує assignment-bound snapshot. Це наявна версійна межа, а не новий historical-detail API.

## Фактично виконані перевірки

| Перевірка | Passed | Failed | Skipped |
| --- | ---: | ---: | ---: |
| Backend RED, новий API regression | 0 | 1 | 0 |
| Backend GREEN: новий тест + Employee Training API | 10 | 0 | 0 |
| Backend retained Menu + dependency + Employee Menu API | 20 | 0 | 0 |
| Frontend RED: новий reader suite | 1 | 2 | 0 |
| Focused reader/overlay/learning Vitest | 15 | 0 | 0 |
| Повний frontend Vitest, 31 файл | 150 | 0 | 0 |
| Playwright reader/overlay, 1440/768/375px | 6 | 0 | 0 |
| Local content structural/source validations | 377 | 0 | 0 |

Backend runs перетинаються одним тестом; числа не додаються як один suite. RED API впав
саме через відсутній module_id; UI RED — відсутні module link та named button.
Початковий sandbox Vitest не стартував через spawn EPERM (не RED); дозволений локальний
запуск поза sandbox дав справжній RED. Початковий tsc мав заборону запису build cache та
DOM globals у новому browser test; string evaluate й дозволений rerun усунули їх.
Content helper спершу мав syntax error, потім помилку Counter та два відсутні review mappings;
після виправлення перевірки вище пройшли. Жоден failed run не перейменовано на passed.

TypeScript, Vite build, ESLint, global Prettier, scoped Ruff format/check, scoped mypy
(4 files) і git diff --check пройшли. Збірка JS приблизно 538 kB; відомий розмір bundle
залишається. Повний backend coverage та повний Playwright suite не повторювалися:
запущено пропорційні API/reader/overlay регресії. Test DB guarded APP_ENV=test/horeca_test,
наявна схема 0021; non-test migration не виконувалася.

Команди: наявні Node CLIs vitest/vite/tsc/eslint/prettier/playwright з frontend,
`vitest run --maxWorkers=1 --reporter=dot`, `playwright test e2e/lesson-structure.spec.ts
e2e/lesson-menu-overlay.spec.ts --workers=1`; наявний Python 3.12 venv, pytest через
локальний guarded launcher, Ruff/mypy. Dependencies не встановлювалися.

## Content impact і конкретний наступний gate

Локальні артефакти: outputs/lesson-ux/content-plan.json, preview-data.json,
content-checks.json, ux-only.patch та baseline/inherited/UX manifests.
Preview використовує реальний frontend build і локальний read-only fixture server;
fake session/progress явно позначені. Це не доказ real backend content publication.

Усі 308 primary items присутні рівно один раз, усі 32 категорії збережені.
Старі 40 lesson-source occurrences з перших чотирьох уроків збережені у явному повторенні.
Додатково два authored sources морозива виявлені у lesson «Вино, коктейлі та інші позиції»:
вони теж залишені окремим повторенням. Це навмисна compatibility межа; довільно видаляти їх
або міняти Final bucket policy не можна. Усі 60 локальних authored references знайдені
в primary/review відповідного уроку. Це не повний аудит live published QuestionSourceLink.

Перед hosted content approval необхідно завершити read-only Admin mapping точного current
Training hierarchy/revision і всіх published question links. Потім сформувати точний Draft
clone/edit payload зі збереженими stable IDs та evidence, перевірити assessment configuration
цільової версії й rollout impact. Для чотирьох матеріально змінених уроків явно вибрати
preserve_completion, якщо Denys прийме цей impact; не припускати автоматичне перенесення
банків, циклів або assignments. Публікація і rollout — окремі дії.

Нові commit/push/PR/deploy, hosted Draft/content write, grants, emails не виконувалися.
Наступний безпечний крок — перегляд локального UI та source packet, дозвіл на Linear запис;
після exact mapping окреме конкретне content/rollout та delivery approval.
