import { defineRailway, github, postgres, preserve, project, service } from "railway/iac";

const repository = "GarnikSacsha/HorecaFam-";

const sharedBackendEnvironment = {
  APP_ENV: "production",
  LOG_LEVEL: "INFO",
  MFA_ENCRYPTION_KEYS: preserve(),
  AUTH_THROTTLE_HMAC_KEY: preserve(),
  INVITATION_TOKEN_HMAC_KEYS: preserve(),
  PASSWORD_RESET_TOKEN_HMAC_KEYS: preserve(),
  SESSION_COOKIE_SECURE: "true",
  SESSION_COOKIE_SAMESITE: "lax",
};

export default defineRailway(() => {
  const database = postgres("postgres");

  const api = service("api", {
    source: github(repository, { branch: "main" }),
    root: "backend",
    healthcheck: "/api/v1/health",
    env: {
      ...sharedBackendEnvironment,
      DATABASE_URL: database.env.DATABASE_URL,
      PORT: "8000",
      CORS_ALLOWED_ORIGINS: preserve(),
      STORAGE_BUCKET: preserve(),
      STORAGE_ENDPOINT_URL: preserve(),
      STORAGE_REGION: preserve(),
      STORAGE_ACCESS_KEY_ID: preserve(),
      STORAGE_SECRET_ACCESS_KEY: preserve(),
    },
  });

  const worker = service("worker", {
    source: github(repository, { branch: "main" }),
    root: "backend",
    start: "python -m app.worker",
    env: {
      ...sharedBackendEnvironment,
      DATABASE_URL: database.env.DATABASE_URL,
      PUBLIC_APP_URL: preserve(),
      RESEND_API_KEY: preserve(),
      EMAIL_FROM_ADDRESS: preserve(),
      WORKER_ID: preserve(),
      WORKER_IDLE_SECONDS: "1",
      WORKER_HEARTBEAT_INTERVAL_SECONDS: "15",
    },
  });

  const web = service("web", {
    source: github(repository, { branch: "main" }),
    root: "frontend",
    env: {
      PORT: "8080",
      API_UPSTREAM: "http://api.railway.internal:8000",
    },
  });

  return project("HoReCa Training Platform", {
    resources: [database, api, worker, web],
  });
});
