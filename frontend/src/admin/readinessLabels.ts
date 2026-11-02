// Human-readable Ukrainian labels for assessment readiness states and server codes.
// Raw codes stay machine contracts; admins see plain language instead.

const statusLabels: Record<string, string> = {
  ready: "Готово",
  warning: "Є зауваження",
  blocked: "Заблоковано",
  processing: "Обробляється",
};

const codeLabels: Record<string, string> = {
  REPEAT_ROTATION_LIMITED: "Мало питань для різних варіантів при повторній спробі",
  INSUFFICIENT_QUESTION_POOL: "Недостатньо перевірених питань",
  INSUFFICIENT_BUCKET_POOL: "Недостатньо питань в одній із категорій іспиту",
  ASSESSMENT_NOT_CONFIGURED: "Перевірку для цього уроку ще не налаштовано",
  ASSESSMENT_NOT_READY: "Перевірка ще не готова",
  FINAL_EXAM_NOT_CONFIGURED: "Підсумковий іспит ще не налаштовано",
  SOURCE_NOT_ELIGIBLE: "Джерело питань не підходить",
  TRAINING_INCOMPLETE: "Навчання ще не завершено",
  PRACTICE_INCOMPLETE: "Практику ще не пройдено",
  PRACTICE_UNAVAILABLE: "Практика недоступна",
};

export function readinessStatusLabel(status: string): string {
  return statusLabels[status] ?? status;
}

export function readinessCodeLabel(code: string): string {
  return codeLabels[code] ?? "Потрібна перевірка налаштувань";
}
