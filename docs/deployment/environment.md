# Deployment environment inventory

CRA-119 separates API, worker, frontend, PostgreSQL, and private object storage into explicit
runtime boundaries. Values below are names only; real credentials stay in the deployment provider
and ignored local files.

## Shared backend variables

| Variable | Required by | Purpose |
| --- | --- | --- |
| `APP_ENV` | API, worker | `staging` or `production` outside local/test execution. |
| `DATABASE_URL` | API, worker, migration job | Async PostgreSQL URL using `postgresql+asyncpg`. |
| `LOG_LEVEL` | API, worker | Structured application log threshold. |
| `MFA_ENCRYPTION_KEYS` | API | Ordered encryption-key rotation set. |
| `AUTH_THROTTLE_HMAC_KEY` | API | Authentication throttle identity protection. |
| `INVITATION_TOKEN_HMAC_KEYS` | API, worker | Ordered invitation-token derivation keys. |
| `PASSWORD_RESET_TOKEN_HMAC_KEYS` | API, worker | Ordered password-reset-token derivation keys. |
| `CORS_ALLOWED_ORIGINS` | API | Exact credentialed browser origins; wildcard is forbidden. |
| `SESSION_COOKIE_SECURE` | API | Must be `true` outside development. |
| `SESSION_COOKIE_SAMESITE` | API | Cookie cross-site policy. |
| `STORAGE_BUCKET` | API | Private training asset bucket. |
| `STORAGE_ENDPOINT_URL` | API | Private S3-compatible endpoint. |
| `STORAGE_REGION` | API | Storage region, default `auto`. |
| `STORAGE_ADDRESSING_STYLE` | API | S3 addressing: `auto` (default), `virtual`, or `path`. Use `virtual` for the verified Railway staging bucket. |
| `STORAGE_ACCESS_KEY_ID` | API | Private storage credential identifier. |
| `STORAGE_SECRET_ACCESS_KEY` | API | Private storage credential secret. |

The storage endpoint remains the provider endpoint without a bucket prefix. With `virtual`,
the SDK places the bucket in the hostname for signed POST uploads, object inspection and GET
downloads. `path` places it in the URL path; `auto` retains SDK selection. Region `auto` is a
separate setting. Choose the style from the actual bucket's provider metadata, not its display
name. See [Railway bucket access](https://docs.railway.com/storage-buckets) and
[Boto3 S3 configuration](https://docs.aws.amazon.com/boto3/latest/guide/configuration.html).
This setting does not configure bucket CORS or prove live upload acceptance; staging still
requires an authorized browser upload/download check.

## Worker-only variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `PUBLIC_APP_URL` | yes | HTTPS browser origin used to build invitation and reset links. |
| `RESEND_API_KEY` | yes | Resend server-side API credential. |
| `EMAIL_FROM_ADDRESS` | yes | Verified sender, including optional display name. |
| `WORKER_ID` | yes | Stable process identity visible in Job leases and logs. |
| `WORKER_IDLE_SECONDS` | no | Empty-queue polling interval; default `1`. |
| `WORKER_HEARTBEAT_INTERVAL_SECONDS` | no | Lease heartbeat interval; default `15`. |

Provider secrets are never browser variables. The frontend uses same-origin `/api` requests and
therefore needs no public API URL or secret at build time. Railway-provided service variables and
PostgreSQL references are defined at provisioning time; this repository does not contain their
values.
