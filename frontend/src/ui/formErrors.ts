import { ApiError } from "../api/client";
import type { FieldError } from "../api/contracts";

export function formErrors(error: unknown, fallbackField: string): FieldError[] {
  if (error instanceof ApiError) {
    if (error.fieldErrors.length > 0) return error.fieldErrors;
    return [{ field: fallbackField, code: error.code, message: error.message }];
  }
  return [
    {
      field: fallbackField,
      code: "UNEXPECTED_ERROR",
      message: "Сталася неочікувана помилка. Повторіть спробу.",
    },
  ];
}

export function fieldError(errors: FieldError[], field: string): string | undefined {
  return errors.find((error) => error.field === field)?.message;
}
