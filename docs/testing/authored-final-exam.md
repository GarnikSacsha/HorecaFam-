# CRA-272 — авторські питання та нова версія фінального іспиту

## Погоджені локальні checkpoints — 22.09.2026

Після перевірки Denys дозволив обидва коміти оновленої карти. Код і тести
зафіксовано як `4504cc0` у `codex/cra-272-authored-final`; цей documentation checkpoint
охоплює лише цей звіт, STATUS та delivery report. Стан «коміти не дозволені» нижче
є попереднім етапом підготовки. Push, deployment та content writes не погоджені.
12 staged paths збіглися з перевіреним кодом і sealed manifest; cached diff check
пройшов. Повторних поведінкових змін немає, тести тільки заради коміту не повторювалися.

Дозвіл Denys від 21.09.2026: локальна реалізація погодженого розширення API та
відбору 20 питань за квотами 10/4/3/3. [Обмежена задача й контракт](https://linear.app/craftspacee/issue/CRA-272).
Коміти, публікація контенту та deployment не входять у цей дозвіл.

## Наступна перевірка у новому worktree — 22.09.2026

Виявлено й виправлено повтор попереднього іспиту після зміни AssessmentVersion.
PostgreSQL RED довів перетин; GREEN перевірив 60 synthetic питань, Failed 13/20,
нову версію та наступні 20 без повтору. Попередній Passed 19/20 scenario збережено
окремим параметром. Пошук попередньої спроби curated Final тепер охоплює stable
Assessment, frequency лишається в межах поточної версії.

Свіжий заключний gate: **52 passed, 0 failed, 0 skipped**; Ruff check/format
(273 файли), mypy (250 source files), diff --check пройшли. Початкові 51-test
baseline та 1-test GREEN перетинаються з ним. Нижче залишені попередні результати
першої реалізації, а не повторно виконані тести.

[Пакет доставки](../deployment/authored-final-exam-cra-272.md) містить точний manifest,
обмеження, content/Training rollout порядок та оновлену карту **двох** комітів.
Вона замінює попередні три межі нижче: спільні schema/routes/tests потребують обох
сервісів та publication guard, тому implementation зібрано в один цілісний
перевірений checkpoint; документація — другий. Коміти досі не дозволені.

## Поведінка та API

Обидва нові POST розташовані під
`/api/v1/organizations/{organization_id}/locations/{location_id}` і вимагають
чинну Admin-сесію, CSRF та `Idempotency-Key`.

- `/question-candidates/authored`: `training_version_id`, `lesson_version_id`,
  звичайні `prompt_payload`, `answer_payload`, `explanation_payload`.
  `explanation_payload.authoring` містить `menu_version_id`, `menu_item_version_id`,
  дослівну `source_quote` та `option_rationales` для всіх чотирьох stable keys.
  Рівно чотири унікальні варіанти, один чинний ключ, `selection_mode=single`.
  Результат — кандидат `needs_review`; звичайний approve залишається межею публікації.
- `/training-versions/{version_id}/final-exam/versions`: поточний
  `expected_assessment_version_id` і `policy` з `question_version_ids` та `buckets`.
  Ключі bucket: `food=10`, `drinks=4`, `desserts=3`, `other=3`; кожен містить
  непересічні `category_ids` саме залежного Menu Version. Стратегія —
  `curated_category_quotas_v1`. Приймаються лише чинні опубліковані питання цього Training.

Джерело авторського питання має бути перевіреним описом Published Menu і входити
до вказаного уроку Published Training. Fingerprint охоплює джерело, формулювання,
ключі та підстави; повторна перевірка перед approve відхиляє змінене джерело.
Одобрення авторських питань не додає їх до старого legacy Final: потрібне
явне створення нової версії банку. Звичайний lesson/Practice review збережено.
Структурна перевірка та цитата не доводять семантичну правильність відповіді:
її й правдоподібність дистракторів перевіряє людина під час review.
Підстави зберігаються лише у кандидата; Published Question і Employee snapshots
не отримують `authoring`. Стара заборона редагувати options/answer keys не послаблена.

Новий банк записується в окремий AssessmentVersion у наявних таблицях.
Жодної нової залежності або міграції. Старі версії, результати й сертифікація
не переписуються; активна спроба продовжує використовувати власний snapshot,
навіть якщо новий банк заблокований. Новий старт обирає найновішу версію.
Прохідний бал лишається 14/20; пояснення — після завершення.

Readiness враховує достатність кожного bucket, показує його лічильники та
блокує нестачу, навіть коли загальна кількість перевищує 20. Ротація спершу
уникає попередньої завершеної спроби, потім обирає рідше використані питання
за історією поточної версії; за недостатнього резерву повертається попередження.
Обов'язкова critical-retake ціль замінює питання всередині свого bucket;
недоступна ціль блокує старт. Нова версія сама не дозволяє перескладання
вже сертифікованому працівнику. `other` об'єднує категорії вина/коктейлів/морозива;
окремої гарантованої квоти 1/1/1 усередині цих трьох місць немає.

## Межі майбутніх комітів

Git index не змінено. Селективні межі, без `git add .`:

1. `feat: add source-linked authored question candidates`: новий
   `backend/app/services/question_authoring.py`; зміни авторського контракту в
   `backend/app/schemas/assessment.py`, `backend/app/api/routes/assessments.py`,
   `backend/app/services/question_generation.py`, `backend/app/services/question_review.py`;
   відповідні authoring hunks у нових API/unit/integration tests нижче.
2. `feat: configure versioned final exam quotas`: новий
   `backend/app/services/final_exam_configuration.py`; зміни в
   `backend/app/services/final_exam_readiness.py`, `backend/app/services/final_exam_attempts.py`;
   решта schema/routes/test hunks цього контракту.
3. `docs: record authored final exam verification`: цей файл і `STATUS.md`.

Спільні тестові файли для меж 1–2:
`backend/tests/unit/test_authored_final_contract.py`,
`backend/tests/unit/test_final_exam_quotas.py`,
`backend/tests/api/test_authored_final_api.py`,
`backend/tests/integration/test_authored_final_exam.py`.
Перед комітами спільні файли треба розділити за логічними hunks і повторити
перевірки кожного checkpoint; дозвіл на коміти ще не надано.

## Перевірки та окремий review

- RED: 1 тест API-контракту впав через відсутній endpoint.
- RED: 1 PostgreSQL-тест старої активної спроби впав з `ASSESSMENT_NOT_READY`
  після появи нового заблокованого банку; виправлено пріоритет resume.
- RED під час fresh review: 1 тест довів, що approve авторських питань передчасно
  додає їх до legacy Final (20 замість 0). Авторську family виключено з legacy
  readiness; вона дозволена лише в явно створеній curated версії.
- Перший PostgreSQL-прогін: 6 setup failures через помилковий `menu_id` у
  тестовій фабриці; це не RED поведінки. Виправлено відповідно до чинної моделі.
- Окремий end-to-end service test спочатку мав неправильну форму answer DTO;
  виправлено на чинний `recognition` submission. Після цього створення, approve,
  нова версія, старт, 20 відповідей і finish дали 19/20 та 9500 basis points.
- Основний суміжний прогін: **97 passed, 0 failed, 0 skipped**, PostgreSQL 16,
  лише `APP_ENV=test` і окрема test DB. Охоплює authored/Final/Practice/reference
  families/generated review/retakes/family isolation/Admin API.
- Після цього додано негативні schema cases й focused critical-retake перевірку,
  уточнено category ownership, readiness evidence та блокування номера версії.
  Focused rerun: **45 passed, 0 failed, 0 skipped**. Набори перетинаються з 97;
  результати не підсумовуються як унікальні тести. Додатковий повтор одного
  розширеного lifecycle test пройшов: нова версія після 95% зберігає попередній
  canonical result/certification і не дозволяє автоматичне перескладання.
  Після уточнення legacy publication boundary: **26 passed, 0 failed, 0 skipped**
  у суміжному gate authored lifecycle/generated review/quota/readiness.
- Ruff check пройшов; Ruff format: 273 файли; mypy: 250 source files.

Окремий fresh review після основного GREEN перевірив: scope/CSRF, ідемпотентність,
source bindings і stale check, відсутність authoring/ключів у ранній відповіді
Employee, незалежність старого snapshot, curated allowlist, конкуренцію номерів
версій та critical-retake replacement. Виявлені уточнення внесено в межах задачі.
Повне coverage, браузерний прогін і hosted acceptance не виконувалися; frontend
не змінено. Це локальна API-реалізація, не підтвердження публікації 60 питань.

## Наступний окремий етап

Після погодження доставки коду: зіставити локальні source IDs з реальними UUID,
розширити/перевірити навчальні прив'язки для всіх вибраних позицій, створити
кандидатів через новий API, перевірити кожне питання та опублікувати новий банк
окремо погодженою операцією. Чинні чотири уроки не покривають автоматично всі
60 авторських питань. Не обходити цей gate прямим записом у БД. Авторський UI,
публікація та реальне перескладання залишаються поза локальним етапом.
