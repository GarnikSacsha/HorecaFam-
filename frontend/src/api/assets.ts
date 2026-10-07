import { createIdempotencyKey, type ApiClient } from "./client";
import type { AssetUploadIntentResponse, TrainingAssetResponse } from "./contracts";

export async function uploadPrivateImage(
  client: ApiClient,
  base: string,
  csrfToken: string,
  file: File,
  onVerify?: () => void,
): Promise<TrainingAssetResponse> {
  const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  const checksum = Array.from(new Uint8Array(digest), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
  const intent = await client.request<AssetUploadIntentResponse>(`${base}/upload-intents`, {
    method: "POST",
    body: { file_name: file.name, mime_type: file.type, size_bytes: file.size, sha256: checksum },
    csrfToken,
    idempotencyKey: createIdempotencyKey(),
  });
  const form = new FormData();
  Object.entries(intent.upload_fields).forEach(([key, value]) => form.append(key, value));
  form.append("file", file);
  const upload = await fetch(intent.upload_url, { method: "POST", body: form });
  if (!upload.ok) throw new Error("upload failed");
  onVerify?.();
  return client.request<TrainingAssetResponse>(`${base}/${intent.asset_id}/complete`, {
    method: "POST",
    body: { sha256: checksum },
    csrfToken,
    idempotencyKey: createIdempotencyKey(),
  });
}
