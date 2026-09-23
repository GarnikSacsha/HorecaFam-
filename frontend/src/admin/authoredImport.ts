import type { ApiClient } from "../api/client";
import type {
  MenuItemListResponse,
  MenuItemResponse,
  MenuVersionDetail,
  TrainingVersionDetail,
  QuestionCandidateEditedPayload,
} from "../api/contracts";

export const quotas = { food: 10, drinks: 4, desserts: 3, other: 3 } as const;
export type Bucket = keyof typeof quotas;
export interface AuthoringEvidence {
  menu_version_id: string;
  menu_item_version_id: string;
  source_quote: string;
  option_rationales: Record<string, string>;
}
export interface AuthoredRequest extends QuestionCandidateEditedPayload {
  training_version_id: string;
  lesson_version_id: string;
  explanation_payload: QuestionCandidateEditedPayload["explanation_payload"] & {
    authoring: AuthoringEvidence;
  };
}
export interface ImportRow {
  source_name: string;
  category: string;
  lesson_title?: string;
  bucket: Bucket;
  prompt_payload: AuthoredRequest["prompt_payload"];
  answer_payload: AuthoredRequest["answer_payload"];
  explanation_payload: QuestionCandidateEditedPayload["explanation_payload"];
  source_quote: string;
  option_rationales: Record<string, string>;
}
export interface PreparedQuestion {
  source: string;
  lesson: string;
  categoryId: string;
  bucket: Bucket;
  body: AuthoredRequest;
}
export interface SourceCatalogue {
  menu: MenuVersionDetail;
  training: TrainingVersionDetail;
  items: MenuItemResponse[];
}
export interface QuotaPolicy {
  strategy: "curated_category_quotas_v1";
  question_version_ids: string[];
  buckets: Array<{ key: Bucket; count: number; category_ids: string[] }>;
}
const object = (value: unknown): value is Record<string, unknown> =>
  !!value && typeof value === "object" && !Array.isArray(value);
const bounded = (value: unknown, max: number): value is string =>
  typeof value === "string" && !!value.trim() && value.length <= max;
const uuid = (value: unknown): value is string =>
  typeof value === "string" && /^[\da-f]{8}(?:-[\da-f]{4}){3}-[\da-f]{12}$/i.test(value);

export function parseImport(text: string): ImportRow[] {
  if (text.length > 1_000_000) throw new Error("Пакет завеликий: максимум 1 МБ.");
  let input: unknown;
  try {
    input = JSON.parse(text);
  } catch {
    throw new Error("Перевірте формат JSON пакета.");
  }
  if (
    !object(input) ||
    !Array.isArray(input.questions) ||
    !input.questions.length ||
    input.questions.length > 100
  )
    throw new Error("Пакет має містити questions: від 1 до 100 питань.");
  return input.questions.map((row: unknown, index: number) => {
    const invalid = () =>
      new Error(
        `Питання ${index + 1}: потрібні джерело, категорія, група, чотири різні варіанти, одна відповідь, цитата та обґрунтування кожного варіанта.`,
      );
    if (
      !object(row) ||
      !bounded(row.source_name, 500) ||
      !bounded(row.category, 500) ||
      typeof row.bucket !== "string" ||
      !Object.hasOwn(quotas, row.bucket) ||
      (row.lesson_title !== undefined && !bounded(row.lesson_title, 500)) ||
      !bounded(row.source_quote, 4000) ||
      !object(row.option_rationales) ||
      !object(row.prompt_payload) ||
      !object(row.answer_payload) ||
      !object(row.explanation_payload)
    )
      throw invalid();
    const prompt = row.prompt_payload;
    const answer = row.answer_payload;
    if (
      prompt.locale !== "uk" ||
      prompt.selection_mode !== "single" ||
      !bounded(prompt.stem, 500) ||
      !Array.isArray(prompt.options) ||
      prompt.options.length !== 4 ||
      !prompt.options.every(
        (option: unknown) =>
          object(option) && bounded(option.stable_key, 100) && bounded(option.text, 200),
      ) ||
      row.explanation_payload.locale !== "uk" ||
      !bounded(row.explanation_payload.text, 1000)
    )
      throw invalid();
    const options = prompt.options as Array<{ stable_key: string; text: string }>;
    const keys = options.map((option) => option.stable_key);
    if (
      new Set(keys).size !== 4 ||
      new Set(options.map((option) => option.text.trim().toLocaleLowerCase("uk"))).size !== 4 ||
      !Array.isArray(answer.correct_option_keys) ||
      answer.correct_option_keys.length !== 1 ||
      !keys.includes(answer.correct_option_keys[0] as string) ||
      Object.keys(row.option_rationales).length !== 4 ||
      !keys.every((key) => bounded((row.option_rationales as Record<string, unknown>)[key], 1000))
    )
      throw invalid();
    return {
      source_name: row.source_name,
      category: row.category,
      lesson_title: row.lesson_title,
      bucket: row.bucket as Bucket,
      prompt_payload: {
        locale: "uk",
        selection_mode: "single",
        stem: prompt.stem,
        options: options.map(({ stable_key, text }) => ({ stable_key, text })),
      },
      answer_payload: { correct_option_keys: [answer.correct_option_keys[0] as string] },
      explanation_payload: { locale: "uk", text: row.explanation_payload.text },
      source_quote: row.source_quote,
      option_rationales: Object.fromEntries(
        keys.map((key) => [key, (row.option_rationales as Record<string, string>)[key]]),
      ),
    };
  });
}

export async function loadCatalogue(
  client: ApiClient,
  base: string,
  menuId: string,
  trainingId: string,
): Promise<SourceCatalogue> {
  const [menu, training] = await Promise.all([
    client.request<MenuVersionDetail>(`${base}/menu-versions/${menuId}`),
    client.request<TrainingVersionDetail>(`${base}/training-versions/${trainingId}`),
  ]);
  if (
    menu.status !== "published" ||
    training.status !== "published" ||
    training.menu_version_id !== menu.id
  )
    throw new Error("Опубліковане навчання має бути прив’язане до поточного меню.");
  const items: MenuItemResponse[] = [];
  const seen = new Set<string>();
  let cursor: string | null = null;
  do {
    const params = new URLSearchParams({ limit: "100" });
    if (cursor) params.set("cursor", cursor);
    const page = await client.request<MenuItemListResponse>(
      `${base}/menu-versions/${menuId}/items?${params}`,
    );
    if (page.revision !== menu.revision || (page.next_cursor && seen.has(page.next_cursor)))
      throw new Error("Меню змінилося. Перевірте пакет повторно.");
    items.push(...page.items);
    cursor = page.next_cursor;
    if (cursor) seen.add(cursor);
  } while (cursor);
  return { menu, training, items };
}

export function bindQuestions(rows: ImportRow[], catalogue: SourceCatalogue): PreparedQuestion[] {
  const { menu, training, items } = catalogue;
  const categories = menu.sections.flatMap((section) => section.categories);
  const lessons = training.modules.flatMap((module) => module.lessons);
  const bodies = new Set<string>();
  const groups = new Map<string, Bucket>();
  return rows.map((row, index) => {
    const matches = items.filter(
      (item) =>
        item.name_uk === row.source_name &&
        categories.some(
          (category) => category.id === item.category_id && category.name_uk === row.category,
        ),
    );
    if (matches.length !== 1)
      throw new Error(
        `Питання ${index + 1}: джерело «${row.source_name}» не знайдено однозначно в категорії «${row.category}».`,
      );
    const item = matches[0];
    if (!item.verified_at || !item.description_uk?.includes(row.source_quote))
      throw new Error(`Питання ${index + 1}: цитата не збігається з перевіреним описом меню.`);
    const bound = lessons.filter(
      (lesson) =>
        (!row.lesson_title || lesson.title_uk === row.lesson_title) &&
        lesson.content_blocks.some((block) => block.menu_item_id === item.item_id),
    );
    if (bound.length !== 1)
      throw new Error(
        `Питання ${index + 1}: «${row.source_name}» має ${bound.length} відповідних уроків. Додайте картку до уроку в навчальних матеріалах або уточніть lesson_title в пакеті.`,
      );
    if (groups.has(item.category_id) && groups.get(item.category_id) !== row.bucket)
      throw new Error("Одна категорія не може належати до різних груп іспиту.");
    groups.set(item.category_id, row.bucket);
    if (!bound[0].lesson_version_id)
      throw new Error("Сервер не повернув версію уроку. Оновіть API перед імпортом.");
    const body: AuthoredRequest = {
      training_version_id: training.id,
      lesson_version_id: bound[0].lesson_version_id,
      prompt_payload: row.prompt_payload,
      answer_payload: row.answer_payload,
      explanation_payload: {
        ...row.explanation_payload,
        authoring: {
          menu_version_id: menu.id,
          menu_item_version_id: item.item_version_id,
          source_quote: row.source_quote,
          option_rationales: row.option_rationales,
        },
      },
    };
    const identity = JSON.stringify(body);
    if (bodies.has(identity)) throw new Error(`Питання ${index + 1}: дублікат у пакеті.`);
    bodies.add(identity);
    return {
      source: item.name_uk,
      lesson: bound[0].title_uk,
      categoryId: item.category_id,
      bucket: row.bucket,
      body,
    };
  });
}

export function parsePolicy(text: string): QuotaPolicy {
  let value: unknown;
  try {
    value = JSON.parse(text);
  } catch {
    throw new Error("Перевірте JSON конфігурації іспиту.");
  }
  if (
    !object(value) ||
    value.strategy !== "curated_category_quotas_v1" ||
    !Array.isArray(value.question_version_ids) ||
    value.question_version_ids.length < 20 ||
    value.question_version_ids.length > 500 ||
    !value.question_version_ids.every(uuid) ||
    new Set(value.question_version_ids).size !== value.question_version_ids.length ||
    !Array.isArray(value.buckets) ||
    value.buckets.length !== 4
  )
    throw new Error("Потрібні 20–500 різних опублікованих питань і чотири групи 10/4/3/3.");
  const categories: string[] = [];
  const keys = new Set<string>();
  for (const bucket of value.buckets) {
    if (
      !object(bucket) ||
      typeof bucket.key !== "string" ||
      !Object.hasOwn(quotas, bucket.key) ||
      keys.has(bucket.key) ||
      bucket.count !== quotas[bucket.key as Bucket] ||
      !Array.isArray(bucket.category_ids) ||
      !bucket.category_ids.length ||
      bucket.category_ids.length > 100 ||
      !bucket.category_ids.every(uuid)
    )
      throw new Error("Групи мають відповідати квотам 10/4/3/3 і містити категорії меню.");
    keys.add(bucket.key);
    categories.push(...bucket.category_ids);
  }
  if (new Set(categories).size !== categories.length)
    throw new Error("Категорії груп не повинні перетинатися.");
  return value as unknown as QuotaPolicy;
}

export async function payloadKey(scope: string, body: unknown): Promise<string> {
  const bytes = new TextEncoder().encode(`${scope}\n${JSON.stringify(body)}`);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return `authored-ui-${Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("")}`;
}
