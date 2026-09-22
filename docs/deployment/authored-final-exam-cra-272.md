# CRA-272 — перевірений локальний пакет доставки

## Оновлення після дозволу на коміти — 22.09.2026

Denys явно погодив два локальні коміти наведеної карти. Перший — `4504cc0`
(`feat: add authored questions and versioned final exam quotas`), рівно 12 paths,
на локальній гілці `codex/cra-272-authored-final` від `4b45108`. Другий checkpoint
додає цей звіт, testing report та STATUS. Вихідний main не змінено.

Manifest і sealed ZIP перевірено повторно; кодовий staged content збігається з
перевіреним worktree та кандидатом з урахуванням лише CRLF/LF. Cached diff check
пройшов. Повторного запуску незмінених 52 tests/Ruff/mypy лише для коміту не було.
Стан detached HEAD/«не закомічено» та запит дозволу нижче — історія підготовки.

Дозвіл не охоплює push, PR, deployment, Linear update чи content writes.
Наступний зовнішній крок потребує окремої авторизації та свіжої remote/live
перевірки; 60 нерозв'язаних application bindings залишаються окремою межею.

Стан 22.09.2026: підготовлено локально, не закомічено, не доставлено, контент не
опубліковано. [CRA-272](https://linear.app/craftspacee/issue/CRA-272) залишається
In Progress. Поточний дозвіл охоплює локальну перевірку, виправлення та підготовку.

## Джерела та Git

Прочитано AGENTS, backend/AGENTS, harness START-HERE/TESTING/SECURITY/CODE-QUALITY/
GIT-WORKFLOW, актуальний Linear START HERE, повну CRA-272 (коментарів немає),
релевантні Final/retake розділи FINAL CRA-12, поточні сервіси/тести,
[попередній звіт](../testing/authored-final-exam.md), STATUS та
[доставку CRA-234](security-fixes-cra-234-delivery.md).
CRA-272 містить пряме погоджене уточнення для нових версій; старий загальний
sampler залишається для legacy. CRA-12 ще не містить окремого розділу CRA-272;
зовнішню синхронізацію в цій задачі не виконано.

Worktree: detached HEAD `4b45108bd4e3e1515dbd59d2d5e2fc77d6c495b9`.
Незакомічений patch перенесено повністю; відновлення з іншого checkout не знадобилося.
Вихідний checkout залишається на main; його файли не редагувалися. Git index не змінено.
Прямий `rtk git ls-remote origin refs/heads/main` не пройшов через недоступний
мережевий proxy. Актуальність віддаленого main перед push треба перевірити повторно;
локальний tracking ref не є свіжою перевіркою GitHub.

## Виявлення, виправлення та свіжі перевірки

На межі AssessmentVersion пошук попередньої завершеної спроби був обмежений новою
версією. При повторному використанні того самого банку нова спроба повторювала
попередні 20 питань попри достатній резерв. PostgreSQL RED підтвердив саме
`Version rollover repeated the previous completed exam` (1 failed, 0 passed/skipped).
Перший запуск того самого сценарію також упав; повтор додав точне повідомлення
до локального XML, а не змінив умову. Це не setup failure.

Для curated policy пошук тепер використовує стабільний Assessment та Employee
через усі його версії; сортування за completed_at та ID робить вибір визначеним.
Least-used частота лишається в поточній версії. Legacy-поведінка не змінена.
Регресія проходить шлях 60 synthetic питань → approve → версія → 13/20 Failed →
наступна версія → retake → 20 питань без перетину. Окремий параметр зберігає
попередній 19/20 lifecycle і заборону автоматичного retake сертифікованому Employee.

Свіжі результати цієї сесії:

| Перевірка | Результат |
| --- | --- |
| Початковий суміжний gate до виправлення | 51 passed, 0 failed, 0 skipped; 141.63 s |
| Цільова регресія після виправлення | 1 passed, 0 failed, 0 skipped; 9.57 s |
| Заключний суміжний gate | 52 passed, 0 failed, 0 skipped; 157.82 s |
| Ruff check | passed |
| Ruff format --check | 273 files passed після форматування двох змінених файлів |
| mypy app tests | 250 source files passed |
| git diff --check | passed |
| Складання/повторна перевірка manifest | 405 файлів; 393 попередніх файли незмінні |
| Локальний контент | 60 різних питань/джерел, 240 варіантів і чернеток підстав; 30/12/8/10 |
| Компілятор без UUID/review | очікуваний BLOCKED для 60 записів; API requests не створено |

Набори перетинаються: 51+1+52 не означає 104 унікальні тести. Попередні 97/45/26
не є результатами цієї сесії. Full coverage, Docker build та hosted acceptance не запускалися.
Початкові два запуски локального PowerShell helper не дійшли до pytest через
UTF-8/PSScriptRoot; це setup failures. Початковий format check після patch позначив
два файли; вони відформатовані, повтор успішний. Перша перевірка контенту зупинилась
на різниці whitespace; причина та виправлення наведені нижче.

Команди з backend, існуючим Python 3.12 та без встановлення залежностей:

```powershell
rtk <existing-python-3.12> -m pytest tests/unit/test_authored_final_contract.py tests/unit/test_final_exam_quotas.py tests/api/test_authored_final_api.py tests/integration/test_authored_final_exam.py tests/integration/test_final_exam_service.py tests/integration/test_question_generation_service.py tests/integration/test_retake_lifecycle.py -q -p no:cacheprovider --tb=no
rtk <existing-python-3.12> -m ruff check .
rtk <existing-python-3.12> -m ruff format --check .
rtk <existing-python-3.12> -m mypy app tests
```

Локальний `outputs/cra-272-preparation/run-checks.ps1` відтворює ці команди з worktree,
використовуючи наявний interpreter вихідного checkout. Test settings завантажені
тільки в процес за процедурою TESTING, з APP_ENV=test та перевіркою dedicated
horeca_test database. Секретні файли не копіювалися та не друкувалися.

Окремий review після GREEN охопив Admin/MFA/CSRF, scope, idempotency fingerprints,
source/lesson checks, приховані authoring поля, legacy admission, curated allowlist,
номер версії/locking, active snapshot, certification і critical-retake replacement.
Семантика відповідей залишається human-review gate. У банку лише description
питання: critical-allergen retake без відповідної цілі має блокуватися; це не
підстава додати непогоджені питання або послабити захист.

## Незмінний кандидат API

Локальні файли: `outputs/cra-272-preparation/candidate/source.zip` і `manifest.json`.

- База: вже доставлений CRA-234 пакет із 399 файлів, SHA-256
  `78b9de3cb5f9ec1d61332a7e4241df9221b08d02c0c2f51bc1c1e193fb49020b`.
- Записаний останній API deployment: `e4ce2e9b-45b1-4692-a15a-e40b33790551`.
  Це історичний перевірений baseline, не свіжа Railway перевірка.
- Кандидат: **405 файлів**, SHA-256
  `8b748d26220311ddc9de114ccd66288f795edc82ab37484efe864e739e6e15bf`.
- Рівно 12 overlay paths із commit map нижче: 6 змінених, 6 нових.
  Решта 393 файли збережені byte-for-byte. Усі non-Markdown файли збігаються з
  перевіреним worktree після нормалізації лише CRLF/LF.
- Три Markdown файли всередині успадковані від попереднього source packet;
  актуальну дозвільну межу описує цей звіт. Tests виконані в worktree, не в ZIP.
- Міграції, dependencies, frontend, worker/cron, Docker/config і вже доставлені
  CRA-237/238/240/271/234 збережені. Photos, outputs, secrets, caches та Git metadata
  не входять у ZIP. Контент-пакет окремий і не призначений для Git/Linear.

`prepare.py` перевіряє baseline ZIP/manifest, збирає детермінований ZIP, перевіряє
parity і відмовляється перезаписувати sealed файл іншим вмістом. Перед доставкою
повторити hash/inventory перевірку. Нові зміни в коді потребують нового кандидата.

## Остаточна карта локальних комітів — ще не дозволена

Дві первісні implementation-межі об'єднані: спільні schema/routes і нові API та
integration файли імпортують обидва сервіси, а authoring потребує виключення з legacy
Final у тому самому readiness модулі. Whole-file staging окремих первісних меж
залишив би неповний checkpoint. Один кодовий commit зберігає перевірену цілісність
контракту та не потребує неперевіреного ручного розрізання hunks.

1. `feat: add authored questions and versioned final exam quotas` — рівно:

   ```text
   backend/app/api/routes/assessments.py
   backend/app/schemas/assessment.py
   backend/app/services/question_authoring.py
   backend/app/services/question_generation.py
   backend/app/services/question_review.py
   backend/app/services/final_exam_configuration.py
   backend/app/services/final_exam_readiness.py
   backend/app/services/final_exam_attempts.py
   backend/tests/api/test_authored_final_api.py
   backend/tests/integration/test_authored_final_exam.py
   backend/tests/unit/test_authored_final_contract.py
   backend/tests/unit/test_final_exam_quotas.py
   ```

   Gate: 52 tests, Ruff check/format, mypy, точний diff та staged inventory.
   Містить попередню реалізацію і нову cross-version rotation регресію/виправлення.
2. `docs: prepare CRA-272 delivery and content transition` — `STATUS.md`,
   `docs/testing/authored-final-exam.md`, цей файл. Залежить від першого checkpoint.
   Documentation-only TDD exception: links, hashes, file inventory і diff hygiene.

Лише після дозволу селективно stage ці списки, перевірити cached diff, виконати
кожний commit. Не stage outputs/Photos; не commit допоміжні локальні скрипти або
клієнтський контент. Push/PR/deploy не входять у дозвіл на локальні коміти.

## Пакет 60 питань

`outputs/cra-272-preparation/content/` містить:

- `authoring-drafts.json`: 60 незмінених погоджених формулювань/варіантів/ключів,
  цитати, 240 нових чернеток rationale, нерозв'язані bindings і execution ledger.
- `source-mapping.json`: по одному рядку на кожне джерело, локальний ID і окремі
  порожні поля справжніх UUID; numeric source_id ніколи не є application UUID.
- `REVIEW.md`: усі питання, цитати та підстави для окремої перевірки.
- `final-policy-draft.json`: 10/4/3/3 та очікувані пули 30/12/8/10; UUID arrays
  порожні, тому це явно не готовий HTTP request.

Оригінальні questions/authored-questions/REVIEW/FINAL-EXAM-PLAN не змінені;
їх SHA-256 збережено у `validation.json`. У шести цитатах відновлено whitespace
із menu-cards snapshot; normalized texts усіх 60 збігаються. Перед POST потрібна
дослівна перевірка вже з актуальною відповіддю застосунку, бо API перевіряє substring,
а локальний snapshot не доводить поточний verified status.

Нові rationale не є новим owner approval. Потрібна перевірка унікальності ключа
та кожного дистрактора. Не перетворювати опис на твердження про повний склад,
алергени або безпечність страви. Stop-list flag збережений для review, не змінений.

`compile-content.py` працює лише офлайн із копією draft: без справжніх UUID,
підтверджених джерел і semantic review він не створює requests. Після заповнення
перевіряє чинні Pydantic DTO, спільний tenant/Training/Menu scope і непересічні
category buckets, явно включає authoring evidence в POST JSON. Final request
формується лише після запису всіх 60 Published QuestionVersion UUID та очікуваної
поточної AssessmentVersion. Сам helper нічого не надсилає. Його positive path із
реальними mappings ще не перевірений; нинішній gate підтвердив fail-closed відмову.

## Порядок майбутнього переносу та межі дозволів

1. **Read-only inventory.** У звичайній Admin-сесії зафіксувати Organization/Location,
   Published Menu/Training, dependency, stable Training ID, lesson IDs, readiness,
   поточний Final ID, активні attempts і результати/сертифікацію. Зіставити всі
   60 позицій за назвою, категорією, дослівним описом і source binding; неоднозначні
   збіги не приймати. Зафіксувати MenuItem та MenuItemVersion окремо, category UUID
   саме MenuVersionCategory. Нині **60/60 application bindings не підтверджені**.
2. **Код.** Після окремого дозволу на API delivery звірити live baseline та settings,
   перевірити sealed manifest, доставити тільки цей source до наявного API.
   Health/routing, Admin read-only readiness/Results і Employee history мають
   зберегти чинний результат. Жодної міграції, frontend/worker/cron доставки або
   content writes на цьому кроці. При live drift зупинити upload і звірити джерело.
3. **Lessons.** Поточні 4 уроки/27 позицій не покривають автоматично 60 джерел.
   Якщо read-only mapping це підтвердить, підготувати Draft наступного Training
   у тому самому stable root, з чинною Menu dependency; Published lessons не
   редагуються. Розподілити всі 60 source bindings так, щоб кожний required lesson
   мав принаймні 5 reviewed questions. Орієнтир чотирьох груп: 30/12/8/10; остаточні
   lesson UUID і правила збереження completion залежать від наявних уроків.
   Не додавати зайві required lessons з недостатнім пулом. Зберегти старий контент.
4. **Окремо погоджена Training publication.** Перевірити Draft readiness, поточні
   revision/base IDs, audience та вплив. Publication архівує попередній Training,
   виконує applicability і готує replacement rollout; можливі assignments/jobs.
   Це не нейтральне завантаження питань. Потрібен конкретний дозвіл на ці наслідки.
   Не confirm rollout автоматично. За потреби узгодити вікно, поки нові lesson pools
   ще готуються. Authoring приймає тільки Published Training, тому зробити все
   до його publication через цей API неможливо.
5. **Кандидати та review.** Лише після дозволу на content writes створити 60
   `question-candidates/authored` у цільовому Published Training. Для кожного зберегти
   idempotency key, exact payload hash, candidate UUID/revision та readback.
   Повтор після timeout — той самий key/body; конфлікт/stale зупиняє рядок.
   Review через звичайний Admin approve; ledger з Published QuestionVersion UUID.
   Approve також змінює lesson/Practice pools, але не legacy Final. Не підміняти
   питання generated candidates, не виконувати прямий DB import.
6. **Новий Final.** Перевірити lesson readiness, Practice >=10 distinct sources,
   усі 60 Published questions поточного Training і buckets 30/12/8/10, квоти
   10/4/3/3. Зчитати поточний AssessmentVersion UUID безпосередньо перед POST.
   Окремо погодити explicit new-version POST: він відразу створює Published version,
   додаткового draft/publish етапу для Final немає. Перевірити allowlist рівно 60,
   threshold 70, feedback after finish, readiness та replay з тим самим key.
7. **Rollout та Employee acceptance.** Для нового Training перевірити rollout
   preview/lesson rules, збереження історії та поточні requirements; confirm лише
   за окремим погодженням. AssessmentVersion сама не переводить старі assignments
   до іншого TrainingVersion. Контрольний новий іспит — лише для дозволеного
   Employee/retake, не автоматично для вже сертифікованого користувача.

Після кожного mutation readback перевіряє resource/revision та фактичний ефект.
До content approval жоден із пунктів 3–7 не виконано. 308-item банк поза scope.

## Відновлення

До будь-яких нових content writes: окремо погоджений API rollback до записаного
CRA-234 deployment не потребує schema downgrade. Не відкочувати міграцію 0020,
web або worker. При невдалому code delivery зупинити перенесення контенту.

Після активації curated AssessmentVersion старий API **не є безпечним автоматичним
rollback**: він не знає нової quota policy та version-selection правил. Потрібен
окремо погоджений forward fix або сумісний відновлювальний кандидат. Для виправлення
банку можна підготувати наступну curated версію з валідними Published питаннями
того самого Training, з новим expected-current guard. Це не переписує history.
Немає підстав вигадувати endpoint відключення/перемикання старої версії.

Після Training publication/rollout просте повернення binary не повертає assignments,
completion rules чи jobs. Зберегти ledger, зупинити нові операції, отримати окреме
рішення відновлення через підтриманий workflow. Старі Attempts/Results/Certification
не видаляти й не редагувати; batch approval не має обіцяного автоматичного undo.

## Наступний конкретний дозвіл

Перший готовий крок — **два селективні локальні коміти за картою вище** після
перевірки актуального diff. Це не дозвіл на push, deployment, Training publication,
review/approve питань або rollout. Перед наступним зовнішнім кроком повторно
перевірити GitHub/live baseline та unresolved application mappings.
