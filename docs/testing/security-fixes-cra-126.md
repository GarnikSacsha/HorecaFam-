# CRA-126: локальне виправлення шести security findings

Дата: 2026-09-08. Задача: [CRA-126](https://linear.app/craftspacee/issue/CRA-126/fix-six-validated-horeca-security-audit-findings).
Базовий HEAD: `2275cee1ae46da708f33a032229e708c73a966c8`, гілка `main`.
Denys явно дозволив публікацію цього звіту до CRA-126, вибіркові коміти та push
2026-09-08. Це продовження тієї самої bounded issue. PR, deployment, виклики
провайдерів і зміни нетестових даних не входять до цього дозволу.
Початковий аудит `f37959a2-c70d-4400-968c-402aaadf65d5` зберігається без змін.

Outcome: **fixed — локальний кандидат для всіх шести findings**. Повний фінальний gate
пройдено: **832 passed, 0 failed, 0 errors, 0 skipped** за **1868.62s**. Додано 23 тести.
Це перевірка локального коду; умови rollout та межі provider evidence наведені нижче.

Попередню публікацію звіту до Linear відхилила автоматична перевірка дозволів.
Після перегляду локального звіту Denys окремо дозволив його публікацію та commit + push.
Цей новий дозвіл замінює попередній стан очікування публікації.
Звіт опубліковано до CRA-126; readback підтвердив текст результатів і явний дозвіл.

## Виконання дозволених комітів — 2026-09-08

1. `6e2665ebe7e0a02cfcf8a1460a975c8b0c8f0026` — assessment family enforcement;
   перед комітом 16 focused tests passed, 0 failed/skipped, 41.77s.
2. `0083ddfe07954ae460c1c5ba679cc4dfffe798ac` — auth budgets, password rotation та Argon2;
   перед комітом 66 focused tests passed, 0 failed/skipped, 177.95s.
3. `034bb5c5eed2aca30c0fe8851c68476f181eb120` — protected asset finalization;
   перед комітом 24 focused tests passed, 0 failed/skipped, 42.22s.
4. Окремий документаційний checkpoint містить цей звіт і підтвердження дозволу.

Ruff format/check, strict mypy та coverage gates повторно пройдені перед публікацією.
Python-source digest збігається з успішним 832-test run; новий повний запуск не потрібен.
Для кожного коміту перевірені selective inventory та `git diff --cached --check`.
Попередні user changes, `Photos/` та runtime artifacts збережені поза комітами.
Push дозволений як звичайний fast-forward до наявного `origin/main`; точний опублікований
endpoint і remote readback записуються до CRA-126 після завершення push. Deployment окремий.

## Межі та докази

| Finding | Вразливий шлях та інваріант | Виправлення і перевірка |
| --- | --- | --- |
| `authorization.assessment-type-confusion` | Employee передавав власний Practice/Final Attempt до Interactive answer/replay. Політика сімейства має перевірятися до читання feedback або мутації. | Спільний `_owned_attempt` перевіряє Assessment type під блокуванням Attempt. Вісім випадків Practice/Final × answer/read/takeover/replay повертають 404 без зміни відповідей, lease та audit. Звичайні Interactive тести збережені. |
| `authentication.mfa-throttle-reset` | Правильний пароль дозволяв створювати новий challenge з п'ятьма новими спробами. Новий challenge не повинен поновлювати бюджет другого фактора. | Account-scoped `mfa` budget охоплює TOTP, enrollment confirmation, recovery verification та regeneration. П'ять помилок блокують наступні спроби на 15 хвилин. Чергування TOTP/recovery та нових login не обходить блокування; після cooldown правильний код працює. Вісім конкурентних перевірок не перевищують бюджет. |
| `authentication.stale-mfa-after-rotation` | Старий challenge залишався придатним після reset/change password. Відкликана password authority не повинна створювати нову Session. | Ротація відкликає всі невикористані challenges. Спільне блокування account серіалізує ротацію та MFA verification; ORM state перечитується після очікування. Перевірені reset, change, конкурентна verification та збереження поточної сесії при change. |
| `authentication.unthrottled-reauthentication` | Session + CSRF дозволяли необмежено перевіряти current password через change. Бюджет має належати account, а не Session. | Спільний `reauth` budget у change та recovery regeneration; помилки фіксуються перед HTTP exception. Після п'яти помилок правильний пароль також отримує 429 до cooldown. Існуючі 401, recent-MFA та session revocation semantics збережені. |
| `availability.synchronous-password-verification` | Argon2 у публічному async login блокував event loop. Криптографія не повинна виконуватися в event-loop thread або створювати необмежену чергу. | HTTP callers використовують async wrapper: два worker slots на процес, fail-fast 429, максимум 1024 символи password, dummy verification та rehash збережені. Cancellation не звільняє слот до завершення worker. Інструментований verifier доводить прогрес event loop та обмеження admission. Зайнятий account у login перевіряється неблокувальним advisory lock. |
| `integrity.mutable-published-assets` | Presigned POST міг перезаписати ready object; client metadata не доводила digest байтів. Опублікований object не повинен бути upload target. | Upload intent використовує окремий source key. Finalization читає не більше очікуваного розміру + 1, перевіряє фактичний SHA-256 і публікує ті самі байти під новим server-only key. Ready/failed/expired replay не видає новий POST. Stateful fake доводить незмінність final object після перезапису source; forged metadata не обходить digest. |

Спільні helpers обрані за наявними викликами, щоб закрити всі відповідні entry points без
нового framework чи залежностей. Session/CSRF/RBAC, tenant ownership, TOTP replay checks,
схеми API та приватний download flow не послаблювалися.

## Перевірка кандидата

Окремий read-only investigator виконав pre-patch boundary review. Після focused GREEN
окремий reviewer виконав єдиний candidate review без rationale чи заяв про успішні тести.
Дві його гіпотези підтверджені новими RED тестами:

- Login очікував account lock до admission і міг утримувати DB connections.
  Тепер зайнятий account одразу повертає `429 AUTH_RATE_LIMITED`.
- Refresh Session втрачав незбережений `last_seen_at`. Тепер після перевірки live Session
  активність поновлюється; тест change на 13-й день та session request на 15-й день проходить.

## Команди та результати

Середовище: Python 3.12.10, наявний `.venv`, native PostgreSQL 16, лише dedicated test database.
Команди pytest виконуються з `backend/` після завантаження наявної test configuration
офіційним PowerShell loader з `.harness/TESTING.md`; значення конфігурації не виводяться.
Усі команди запускаються через `rtk proxy`.

| Етап | Результат |
| --- | --- |
| Базовий `tests/integration/test_database.py` | 1 passed, 0 failed, 0 skipped |
| RED: family matrix | 8 failed; відсутній guard, включно з schema failure на двох read paths |
| RED: перші auth regressions | 3 failed: повторний MFA budget, stale challenge, current-password limit |
| RED: async password admission | 3 failed: відсутня async boundary |
| RED: asset publication | 3 failed: той самий final key / відсутня finalization |
| GREEN: family + adjacent Interactive tests | 16 passed, 0 failed, 0 skipped |
| GREEN: auth/MFA/password/asset/storage/admin, 10 файлів | 65 passed, 0 failed, 0 skipped |
| GREEN: auth regressions + asset immutability + migration round-trip | 8 passed, 0 failed, 0 skipped |
| RED: дві reviewer regressions | 2 failed, 6 deselected |
| GREEN: усі auth regressions + `test_auth_login.py` | 15 passed, 0 failed, 0 skipped |
| `python -m ruff format --check .` | 246 files already formatted |
| `python -m ruff check .` | Passed |
| `python -m mypy app tests` | Passed, 224 source files |
| Перший повний pytest | 816 passed, 0 failed, 16 setup errors, 0 skipped; 1885.69s; ACL тимчасового каталогу Windows |
| `test_coverage_gate.py` після усунення обмеження середовища | 16 passed, 0 failed, 0 skipped; 0.19s |
| Повторний повний pytest | 832 passed, 0 failed, 0 errors, 0 skipped; 1868.62s; exit 0 |
| Statements gate | 11532/12286 = 93.86%, PASS |
| Branches gate | 2064/2574 = 80.19%, PASS |
| Fixed critical aggregate gate | 1319/1471 = 89.67%, PASS |
| Alembic upgrade/current/check після повного набору | Passed; `0019_auth_security_budgets`; no metadata drift |
| Final diff/inventory | `git diff --check` passed; Git index порожній; лише bounded files належать до change map |

Лічильники focused запусків перекриваються; їх не слід додавати як кількість унікальних тестів.
Проміжний auth candidate мав 18 failures через ORM loading/flush, виправлені до GREEN.
Одна команда з помилковим ім'ям `test_invitation_acceptance.py` не запустила жодного тесту;
правильний файл `test_invitations_accept.py` входить до повного набору.
Перший повний запуск зупинився до collection через ACL каталогу `.pytest_cache`;
повторний використовує окремий `outputs/cra126/` для runtime evidence, поза commit map.
Перший повний прогін виконав всі application/migration tests, але 16 тестів coverage helper
не отримали доступ до pytest temp directory. Перенесення temp усередину workspace не допомогло;
окремий запуск цих 16 tests поза обмеженим процесом пройшов. Щоб виконати вимогу
`.harness/TESTING.md` про JSON саме з успішного повного запуску, весь набір запущено повторно
в перевіреному середовищі. JSON першого прогону не використовується як фінальний gate.
Повторний запуск завершився exit 0; `tests.coverage_gate` перевірив саме `verified.json`
із цього запуску, включно з повним inventory Python sources. Пороги не змінювалися.

Фінальна команда:

```powershell
$env:COVERAGE_FILE = '../outputs/cra126/.coverage-verified'
rtk proxy ..\.venv\Scripts\python.exe -m pytest -vv -p no:cacheprovider --basetemp=../outputs/cra126/pytest-temp-full-verified --cov=app --cov-branch --cov-report=term-missing --cov-report=json:../outputs/cra126/verified.json --tb=short --show-capture=no
rtk proxy ..\.venv\Scripts\python.exe -m tests.coverage_gate ../outputs/cra126/verified.json
rtk proxy ..\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
rtk proxy ..\.venv\Scripts\python.exe -m alembic -c alembic.ini current --check-heads
rtk proxy ..\.venv\Scripts\python.exe -m alembic -c alembic.ini check
```

Перед Alembic додатково перевірено рівність `DATABASE_URL` та `TEST_DATABASE_URL` без
виведення значень. SHA-256 впорядкованих відносних шляхів та байтів усіх Python files у
`backend/app`, `backend/tests`, `backend/migrations` до та після повного gate збігається:
`f59ad67039d32f8c9f64faa3d0d1f0788d88258485cdcf9b1908abede07bb184`.
Тому результати стосуються незмінного кандидата, включно з попередніми user changes.

## Контракт і rollout

- Міграція `0019_auth_security_budgets` розширює CHECK дозволених action двома внутрішніми
  значеннями. Її треба застосувати перед запуском нового API. Локальний empty-data round-trip,
  current head та metadata no-drift перевірені. Нетестові міграції не виконувалися.
- Downgrade навмисно не видаляє security budgets. За наявності `mfa`/`reauth` rows старий CHECK
  не встановиться; потрібен окремо погоджений rollback/data plan. Не очищати їх автоматично.
- Старі presigned POST, видані попередньою версією на ready keys, неможливо відкликати цим
  patch. Для rollout потрібно зупинити старі issuers, дочекатися максимальних 15 хвилин дії
  форм та перевірити цілісність раніше опублікованих об'єктів. Автоматичне переписування
  legacy assets та реальний bucket/IAM smoke не виконувалися.
- Storage adapter потребує server-side GetObject/PutObject. Провайдер, bucket permissions,
  reverse-proxy admission, багатопроцесне навантаження і вимірювання RAM/latency тут не перевірялися.
  Два Argon2 slots — межа на процес, не глобальний rate limit кластера.
- Невдалий DB commit після успішного PutObject може залишити недоступний orphan object;
  cleanup є окремою операційною задачею. Виправлення захищає опублікований pointer.
- Frontend не змінювався; frontend/browser/container/provider suites не входять до цього
  backend-only локального gate. API compatibility перевіряється backend API/OpenAPI tests.

## Дозволені вибіркові межі комітів

Це вибірковий inventory чотирьох дозволених комітів.
Усі шляхи нижче від кореня репозиторію.

1. `fix: enforce interactive assessment family`
   — `backend/app/services/interactive_attempts.py`, `backend/app/services/interactive_answers.py`,
   `backend/tests/integration/test_assessment_family_security.py`.
2. `fix: enforce authentication budgets and bound password computation`
   — `backend/app/services/auth_security.py`, `backend/app/services/auth.py`,
   `backend/app/services/mfa_enrollment.py`, `backend/app/services/password_recovery.py`,
   `backend/app/models/auth.py`, `backend/app/models/enums.py`,
   `backend/migrations/versions/0019_auth_security_budgets.py`,
   `backend/tests/api/test_auth_security_regressions.py`,
   `backend/tests/migration/test_auth_security_migration.py`,
   `backend/app/security/passwords.py`, `backend/app/services/invitation_acceptance.py`,
   `backend/tests/unit/test_password_admission.py`.
   Дві початкові межі об'єднані, оскільки async callers і wrapper потрібні разом для GREEN.
3. `fix: finalize private assets into protected objects`
   — `backend/app/services/private_storage.py`, `backend/app/services/training_assets.py`,
   `backend/tests/integration/test_training_assets.py`, `backend/tests/api/test_training_admin_api.py`,
   `backend/tests/integration/test_asset_immutability_security.py`,
   `backend/tests/unit/test_asset_finalization_security.py`.
4. `docs: record CRA-126 security verification`
   — цей файл. Попередні зміни docs, `question_generation.py`, `Photos/`, конфігурація,
   `.env*` та runtime output не належать до CRA-126 commit map.

Для кожної межі потрібні її focused tests, Ruff/mypy та перегляд точного diff; повний gate
вище підтверджує сумісність усього кандидата. Коміти обмежені цим inventory.
