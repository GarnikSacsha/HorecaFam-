/// <reference types="node" />
import { webcrypto } from "node:crypto";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiError, type ApiClient, type RequestOptions } from "../api/client";
import { AdminAuthoredQuestions } from "./AdminAuthoredQuestions";
import {
  bindQuestions,
  parseImport,
  parsePolicy,
  payloadKey,
  type SourceCatalogue,
} from "./authoredImport";

const id = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
const row = {
  source_name: "Суп",
  category: "Перші страви",
  bucket: "food",
  prompt_payload: {
    locale: "uk",
    selection_mode: "single",
    stem: "Що зазначено в описі?",
    options: ["Гарбуз", "Рис", "Буряк", "Картопля"].map((text, i) => ({
      stable_key: String(i),
      text,
    })),
  },
  answer_payload: { correct_option_keys: ["0"] },
  explanation_payload: { locale: "uk", text: "В описі зазначено гарбуз." },
  source_quote: "Суп із гарбуза",
  option_rationales: {
    "0": "Збігається з описом.",
    "1": "Опис називає гарбуз.",
    "2": "Інший продукт.",
    "3": "Інший продукт.",
  },
};
const catalogue = {
  menu: {
    id: id(1),
    status: "published",
    revision: 1,
    sections: [{ categories: [{ id: id(3), name_uk: row.category }] }],
  },
  training: {
    id: id(2),
    status: "published",
    menu_version_id: id(1),
    modules: [
      {
        lessons: [
          {
            id: id(40),
            lesson_version_id: id(4),
            title_uk: "Супи",
            content_blocks: [{ menu_item_id: id(5) }],
          },
        ],
      },
    ],
  },
  items: [
    {
      item_id: id(5),
      item_version_id: id(6),
      category_id: id(3),
      name_uk: "Суп",
      description_uk: "Суп із гарбуза",
      verified_at: "2030-01-01",
    },
  ],
} as SourceCatalogue;
const policy = {
  strategy: "curated_category_quotas_v1",
  question_version_ids: Array.from({ length: 20 }, (_, n) => id(n + 100)),
  buckets: ["food", "drinks", "desserts", "other"].map((key, n) => ({
    key,
    count: [10, 4, 3, 3][n],
    category_ids: [id(20 + n)],
  })),
};

function setup(fail: "create" | "approve" | "final" | null = null) {
  Object.defineProperty(globalThis.crypto, "subtle", {
    value: webcrypto.subtle,
    configurable: true,
  });
  const requests: Array<{ path: string; options?: RequestOptions }> = [];
  let failed = false;
  const candidate = {
    id: id(7),
    training_version_id: id(2),
    lesson_version_id: id(4),
    status: "needs_review",
    revision: 1,
  };
  const client: ApiClient = {
    getSession: vi.fn(),
    request: async <T,>(path: string, options?: RequestOptions): Promise<T> => {
      await Promise.resolve();
      requests.push({ path, options });
      if (path.endsWith("/menu-versions")) return { current_published: catalogue.menu } as T;
      if (path.endsWith("/training-versions")) return { published: catalogue.training } as T;
      if (path.endsWith(`/menu-versions/${id(1)}`)) return catalogue.menu as T;
      if (path.includes("/items?"))
        return { items: catalogue.items, next_cursor: null, revision: 1 } as T;
      if (path.endsWith(`/training-versions/${id(2)}`)) return catalogue.training as T;
      if (path.endsWith("/authored")) {
        if (fail === "create" && !failed) {
          failed = true;
          throw new ApiError(0);
        }
        return candidate as T;
      }
      if (path.endsWith(`/${id(7)}`)) return candidate as T;
      if (path.endsWith("/batch-approve")) {
        if (fail === "approve") throw new ApiError(0);
        return {
          items: [{ candidate: { ...candidate, status: "approved" }, question_version_id: id(8) }],
        } as T;
      }
      if (path.endsWith("/readiness")) return { assessment_version_id: id(9) } as T;
      if (path.endsWith("/final-exam/versions")) {
        if (fail === "final" && !failed) {
          failed = true;
          throw new ApiError(409, { code: "REVISION_CONFLICT" });
        }
        return {
          assessment_version_id: id(10),
          eligible_count: 20,
          status: "ready",
          blocking_codes: [],
        } as T;
      }
      throw new Error(`Unexpected test request ${path}`);
    },
  };
  render(
    <AdminAuthoredQuestions
      client={client}
      base="/organizations/o/locations/l"
      menuId={id(1)}
      trainingId={id(2)}
      csrfToken="synthetic-csrf"
      disabled={false}
      onBusy={() => undefined}
      onRefresh={() => Promise.resolve()}
    />,
  );
  return requests;
}
async function prepareImport(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: "Імпорт авторських питань" }));
  await user.click(screen.getByLabelText("Пакет питань (JSON)"));
  await user.paste(JSON.stringify({ questions: [row] }));
  await user.click(screen.getByRole("button", { name: "Перевірити джерела та показати питання" }));
  await screen.findByText(/Джерела й уроки зіставлено/);
}

describe("authored import boundaries", () => {
  it("binds exact verified source and lesson, preserving rationale in the wire payload", () => {
    const [bound] = bindQuestions(parseImport(JSON.stringify({ questions: [row] })), catalogue);
    expect(bound.body.explanation_payload.authoring.menu_item_version_id).toBe(id(6));
    expect(bound.body.lesson_version_id).toBe(id(4));
    expect(bound.body.explanation_payload.authoring.option_rationales).toEqual(
      row.option_rationales,
    );
  });
  it.each([
    { ...row, answer_payload: { correct_option_keys: ["0", "1"] } },
    { ...row, option_rationales: { "0": "Недостатньо" } },
    { ...row, bucket: "__proto__" },
    {
      ...row,
      prompt_payload: {
        ...row.prompt_payload,
        options: Array(4).fill(row.prompt_payload.options[0]),
      },
    },
  ])("rejects invalid content before network writes", (invalid) => {
    expect(() => parseImport(JSON.stringify({ questions: [invalid] }))).toThrow(/Питання 1/);
  });
  it("blocks absent lessons, ambiguous sources and mismatched quotations", () => {
    const rows = parseImport(JSON.stringify({ questions: [row] }));
    expect(() =>
      bindQuestions(rows, { ...catalogue, training: { ...catalogue.training, modules: [] } }),
    ).toThrow(/0 відповідних уроків/);
    expect(() =>
      bindQuestions(rows, { ...catalogue, items: [...catalogue.items, ...catalogue.items] }),
    ).toThrow(/однозначно/);
    expect(() =>
      bindQuestions([{ ...rows[0], source_quote: "Неправильна цитата" }], catalogue),
    ).toThrow(/цитата/);
  });
  it("rejects duplicate questions and overlapping quota categories", () => {
    const rows = parseImport(JSON.stringify({ questions: [row, row] }));
    expect(() => bindQuestions(rows, catalogue)).toThrow(/дублікат/);
    expect(() =>
      parsePolicy(
        JSON.stringify({
          ...policy,
          buckets: policy.buckets.map((bucket) => ({ ...bucket, category_ids: [id(20)] })),
        }),
      ),
    ).toThrow(/перетинатися/);
    expect(parsePolicy(JSON.stringify(policy)).question_version_ids).toHaveLength(20);
  });
  it("previews without writing, retries creation with identical key/body, then separately reviews", async () => {
    const requests = setup("create");
    const user = userEvent.setup();
    await prepareImport(user);
    expect(requests.every(({ options }) => options?.method !== "POST")).toBe(true);
    await user.click(screen.getByRole("button", { name: "Створити кандидатів" }));
    await screen.findByRole("alert");
    await user.click(screen.getByRole("button", { name: "Створити кандидатів" }));
    await screen.findByText(/Створено кандидатів: 1/);
    const writes = requests.filter(({ path }) => path.endsWith("/authored"));
    expect(writes).toHaveLength(2);
    expect(writes[0].options).toEqual(writes[1].options);
    expect(writes[0].options?.csrfToken).toBe("synthetic-csrf");
    expect(screen.getByRole("button", { name: "Схвалити перевірений пакет" })).toBeDisabled();
    await user.click(screen.getByRole("checkbox", { name: /Перевірено зміст/ }));
    await user.click(screen.getByRole("button", { name: "Схвалити перевірений пакет" }));
    await screen.findByText(/Схвалено 1 питань/);
    expect(requests.filter(({ path }) => path.endsWith("/batch-approve"))).toHaveLength(1);
    expect(requests.filter(({ path }) => path.endsWith("/final-exam/versions"))).toHaveLength(0);
    expect(screen.getByLabelText<HTMLTextAreaElement>("Звіт операції").value).toContain(id(8));
  });
  it("blocks blind approval replay after an uncertain response", async () => {
    setup("approve");
    const user = userEvent.setup();
    await prepareImport(user);
    await user.click(screen.getByRole("button", { name: "Створити кандидатів" }));
    await screen.findByText(/Створено кандидатів: 1/);
    await user.click(screen.getByRole("checkbox", { name: /Перевірено зміст/ }));
    await user.click(screen.getByRole("button", { name: "Схвалити перевірений пакет" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Схвалити перевірений пакет" })).toBeDisabled(),
    );
    expect(await screen.findByText(/Повторне схвалення заблоковано/)).toBeInTheDocument();
  });
  it("pins expected Final version and idempotency across conflict retries; never auto-publishes", async () => {
    const requests = setup("final");
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Нова версія Final Exam" }));
    await user.click(screen.getByLabelText("Конфігурація Final (JSON)"));
    await user.paste(JSON.stringify(policy));
    await user.click(screen.getByRole("button", { name: "Переглянути нову версію" }));
    await screen.findByText("Банк: 20 питань.");
    expect(requests.every(({ options }) => options?.method !== "POST")).toBe(true);
    await user.click(screen.getByRole("checkbox", { name: /Підтверджую публікацію/ }));
    await user.click(screen.getByRole("button", { name: "Опублікувати нову версію Final" }));
    await screen.findByRole("alert");
    await user.click(screen.getByRole("button", { name: "Опублікувати нову версію Final" }));
    await screen.findByText(/Нову версію Final опубліковано/);
    const writes = requests.filter(({ path }) => path.endsWith("/final-exam/versions"));
    expect(writes).toHaveLength(2);
    expect(writes[0].options).toEqual(writes[1].options);
    expect(writes[0].options?.body).toEqual({ expected_assessment_version_id: id(9), policy });
    expect(screen.getByRole("button", { name: "Опублікувати нову версію Final" })).toBeDisabled();
  });
  it("binds replay keys to tenant and exact payload", async () => {
    Object.defineProperty(globalThis.crypto, "subtle", {
      value: webcrypto.subtle,
      configurable: true,
    });
    expect(await payloadKey("a", row)).toBe(await payloadKey("a", row));
    expect(await payloadKey("a", row)).not.toBe(await payloadKey("b", row));
  });
});
