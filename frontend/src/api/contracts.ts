export type MembershipStatus = "pending" | "active" | "disabled";

export interface FieldError {
  field: string;
  code: string;
  message: string;
}

export interface ErrorEnvelope {
  code: string;
  message: string;
  field_errors: FieldError[];
  request_id: string;
}

export interface SessionResponse {
  user: {
    id: string;
    email: string;
    preferred_locale: "uk" | "en";
  };
  session: {
    id: string;
    absolute_expires_at: string;
    mfa_verified: boolean;
  };
  organization_access: Array<{
    organization_id: string;
    membership_status: MembershipStatus | null;
    is_employee: boolean;
    is_organization_admin: boolean;
  }>;
  platform_operator: boolean;
  csrf_token: string;
}

export interface MfaRequiredResponse {
  status: "mfa_required";
  expires_at: string;
}

export interface InvitationValidationResponse {
  status: "valid";
  organization_id: string;
  organization_name: string;
  email_masked: string;
  acceptance_mode: "activate_access" | "accept_existing_account";
  expires_at: string;
}

export type InvitationAcceptanceResponse = SessionResponse & {
  status: "accepted";
  acceptance_mode: "activate_access" | "accept_existing_account";
  membership: {
    id: string;
    organization_id: string;
    employee_profile_id: string;
    status: "pending";
  };
};

export interface OrganizationSummary {
  id: string;
  name: string;
  status: "active" | "archived";
  default_locale: "uk" | "en";
  timezone: string;
}

export interface LocationSummary {
  id: string;
  organization_id: string;
  name: string;
  status: "active" | "archived";
  address: string | null;
  timezone: string;
}

export interface OperationalRoleSummary {
  id: string;
  organization_id: string;
  code: string;
  name_uk: string;
  status: "active" | "archived";
}

export interface EmployeeSummary {
  id: string;
  organization_id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  membership_status: MembershipStatus;
  operational_role: OperationalRoleSummary | null;
  location: LocationSummary | null;
  profile_complete: boolean;
  created_at: string;
  updated_at: string;
}

export interface EmployeeDetail extends EmployeeSummary {
  membership_created_at: string;
  activated_at: string | null;
  disabled_at: string | null;
}

export interface EmployeeListResponse {
  items: EmployeeSummary[];
  next_cursor: string | null;
}

export interface EmployeeLifecycleActionResponse {
  employee_id: string;
  organization_id: string;
  membership_status: "active";
  training_participation_status: "active";
  activated_at: string;
}

export interface OwnEmployeeProfile {
  id: string;
  organization: { id: string; name: string };
  membership_status: MembershipStatus;
  first_name: string | null;
  last_name: string | null;
  operational_role: OperationalRoleSummary | null;
  location: LocationSummary | null;
  profile_complete: boolean;
  updated_at: string;
}

export interface OwnEmployeeProfilesResponse {
  profiles: OwnEmployeeProfile[];
}

export type MenuVersionStatus = "draft" | "published" | "archived";
export type MenuAvailability =
  "available" | "temporarily_unavailable" | "seasonal" | "discontinued";
export type FactDataStatus = "unknown" | "confirmed_none" | "confirmed_present";

export interface MenuCategoryResponse {
  id: string;
  section_id: string;
  stable_code: string | null;
  name_uk: string;
  position: number;
  item_count: number;
}

export interface MenuSectionResponse {
  id: string;
  stable_code: string | null;
  name_uk: string;
  position: number;
  category_count: number;
  categories: MenuCategoryResponse[];
}

export interface MenuVersionSummary {
  id: string;
  menu_id: string;
  organization_id: string;
  location_id: string;
  version_number: number;
  status: MenuVersionStatus;
  base_version_id: string | null;
  revision: number;
  section_count: number;
  category_count: number;
  item_count: number;
  created_at: string;
  published_at: string | null;
  archived_at: string | null;
}

export interface MenuVersionDetail extends MenuVersionSummary {
  sections: MenuSectionResponse[];
}

export interface MenuVersionCollection {
  menu_id: string | null;
  organization_id: string;
  location_id: string;
  current_published: MenuVersionSummary | null;
  draft: MenuVersionSummary | null;
  archived: MenuVersionSummary[];
}

export interface MenuComponentInput {
  id: string | null;
  stable_code: string | null;
  name_uk: string;
  optional: boolean | null;
  position: number;
}

export interface MenuItemResponse {
  item_id: string;
  item_version_id: string;
  version_id: string;
  category_id: string;
  stable_code: string | null;
  name_uk: string;
  description_uk: string | null;
  price_minor: number | null;
  currency: string;
  availability: MenuAvailability;
  position: number;
  component_data_status: FactDataStatus;
  components: Array<
    MenuComponentInput & {
      id: string;
      source_kind: "manual" | "json_import";
      source_reference: string | null;
      verified_at: string | null;
    }
  >;
  allergen_data_status: FactDataStatus;
  allergen_codes: string[];
  source_kind: "manual" | "json_import";
  source_reference: string | null;
  source_item_key: string | null;
  verified_at: string | null;
  delta_kind: "added" | "changed" | "removed" | "unchanged";
  training_impact: "none" | "review" | "required";
  changed_field_codes: string[];
  created_at: string;
  updated_at: string;
}

export interface MenuItemListResponse {
  items: MenuItemResponse[];
  next_cursor: string | null;
  revision: number;
}

export type MenuFindingResolutionAction =
  | "confirm_legitimate"
  | "map_existing"
  | "confirm_removal"
  | "confirm_critical_change"
  | "exclude_source_record";

export interface MenuImportFinding {
  id: string;
  severity: "blocker" | "requires_review" | "warning";
  code: string;
  entity_type: string;
  source_key: string | null;
  message: string;
  resolution_status: "unresolved" | "resolved";
  allowed_actions: MenuFindingResolutionAction[];
  resolution_action: MenuFindingResolutionAction | null;
  target_entity_id: string | null;
  resolution_comment: string | null;
  resolved_at: string | null;
}

export interface MenuImportDetail {
  id: string;
  organization_id: string;
  location_id: string;
  menu_id: string;
  base_menu_version_id: string | null;
  status: "uploaded" | "processing" | "ready_for_review" | "confirmed" | "failed" | "stale";
  review_revision: number;
  source_filename: string;
  source_reference: string | null;
  source_checksum: string;
  section_count: number;
  category_count: number;
  item_count: number;
  added_count: number;
  changed_count: number;
  removed_count: number;
  unchanged_count: number;
  blocker_count: number;
  review_count: number;
  warning_count: number;
  findings: MenuImportFinding[];
  created_at: string;
  confirmed_at: string | null;
  failure_code: string | null;
}

export interface MenuImportConfirmResponse {
  import: MenuImportDetail;
  draft: MenuVersionDetail;
}

export interface MenuReadinessIssue {
  code: string;
  message: string;
  entity_type: string;
  entity_id: string | null;
}

export interface MenuReadinessResponse {
  menu_id: string;
  menu_version_id: string;
  organization_id: string;
  location_id: string;
  revision: number;
  can_publish: boolean;
  blocking_errors: MenuReadinessIssue[];
  warnings: MenuReadinessIssue[];
  required_training_asset_count: number;
  ready_training_asset_count: number;
  applicable_training_content_count: number;
}

export interface MenuPublishResponse {
  published: MenuVersionSummary;
  previous_published_version_id: string | null;
  diff_counts: Record<"added" | "changed" | "removed" | "unchanged", number>;
  training_impact_counts: Record<"none" | "review" | "required", number>;
  applicability: {
    published_content_count: number;
    assignment_count: number;
    notification_count: number;
  };
}

export interface EmployeeMenuCategorySummary {
  id: string;
  section_id: string;
  name: string;
  position: number;
}

export interface EmployeeMenuSectionSummary {
  id: string;
  name: string;
  position: number;
  categories: EmployeeMenuCategorySummary[];
}

export interface EmployeeMenuSummary {
  menu_id: string;
  menu_version_id: string;
  location_id: string;
  version_number: number;
  published_at: string;
  sections: EmployeeMenuSectionSummary[];
}

export interface EmployeeMenuItemSummary {
  item_id: string;
  name: string;
  description_excerpt: string | null;
  category_id: string;
  category_name: string;
  section_id: string;
  section_name: string;
  availability: MenuAvailability;
  price_minor: number | null;
  currency: string;
  content_locale: "uk" | "en";
  translation_fallback: boolean;
}

export interface EmployeeMenuResponse {
  menu: EmployeeMenuSummary | null;
  items: EmployeeMenuItemSummary[];
  next_cursor: string | null;
}

export interface EmployeeMenuItemDetail extends EmployeeMenuItemSummary {
  description: string | null;
  components: Array<{
    name: string;
    optional: boolean | null;
    position: number;
  }>;
  allergen_data_status: FactDataStatus;
  allergens: Array<{
    code: string;
    label: string;
  }>;
}

export type TrainingVersionStatus = "draft" | "published" | "archived";
export type TrainingContentBlockType =
  "heading" | "text" | "list" | "callout" | "menu_item_card" | "image" | "external_video";

export interface TrainingAssetResponse {
  id: string;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  status: "pending_upload" | "ready" | "failed" | "archived";
  ready_at: string | null;
  created_at: string;
}

export interface TrainingContentBlockResponse {
  id: string;
  type: TrainingContentBlockType;
  position: number;
  payload: Record<string, unknown>;
  menu_item_id: string | null;
  asset: TrainingAssetResponse | null;
}

export interface TrainingLessonResponse {
  id: string;
  position: number;
  title_uk: string;
  description_uk: string | null;
  required: boolean;
  estimated_minutes: number | null;
  translation_status_en: "pending" | "ready" | "failed" | "stale" | null;
  content_blocks: TrainingContentBlockResponse[];
}

export interface TrainingModuleResponse {
  id: string;
  domain_type: "menu";
  position: number;
  title_uk: string;
  description_uk: string | null;
  required: boolean;
  translation_status_en: "pending" | "ready" | "failed" | "stale" | null;
  lessons: TrainingLessonResponse[];
}

export interface TrainingVersionSummary {
  id: string;
  training_id: string;
  location_id: string;
  version_number: number;
  status: TrainingVersionStatus;
  revision: number;
  base_version_id: string | null;
  module_count: number;
  lesson_count: number;
  created_at: string;
  published_at: string | null;
  archived_at: string | null;
}

export interface TrainingVersionDetail extends TrainingVersionSummary {
  modules: TrainingModuleResponse[];
  menu_version_id: string | null;
}

export interface TrainingVersionCollection {
  published: TrainingVersionSummary | null;
  draft: TrainingVersionSummary | null;
  archived: TrainingVersionSummary[];
}

export interface TrainingReadinessIssue {
  code: string;
  message: string;
  entity_type: string;
  entity_id: string | null;
}

export interface TrainingReadinessResponse {
  training_id: string;
  training_version_id: string;
  organization_id: string;
  location_id: string;
  revision: number;
  can_publish: boolean;
  blocking_errors: TrainingReadinessIssue[];
  warnings: TrainingReadinessIssue[];
  counts: {
    module_count: number;
    lesson_count: number;
    required_lesson_count: number;
    content_block_count: number;
    required_asset_count: number;
    ready_asset_count: number;
    menu_item_link_count: number;
  };
}

export interface TrainingPublishResponse {
  published: TrainingVersionSummary;
  previous_published_version_id: string | null;
  employee_reference_switched: boolean;
  assignment_count: 0;
  completion_count: 0;
  progress_count: 0;
  rollout_count: 0;
  notification_count: 0;
}

export interface AssetUploadIntentResponse {
  asset_id: string;
  upload_url: string;
  upload_fields: Record<string, string>;
  expires_at: string;
}

export interface EmployeeTrainingSummary {
  id: string;
  version_number: number;
  published_at: string;
}

export type EmployeeTrainingAssignmentStatus = "assigned" | "in_progress" | "completed";

export interface EmployeeTrainingAssignmentSummary {
  id: string;
  status: EmployeeTrainingAssignmentStatus;
  assigned_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface TrainingProgressResponse {
  required_lesson_count: number;
  completed_required_lesson_count: number;
  percentage: number;
  is_complete: boolean;
}

export type EmployeeTrainingNextAction = "open_lesson" | "review_training" | "none";

export interface EmployeeTrainingModuleSummary {
  id: string;
  domain_type: "menu";
  title: string;
  description: string | null;
  position: number;
  required: boolean;
  lesson_count: number;
  content_locale: "uk" | "en";
  translation_fallback: boolean;
}

export interface EmployeeTrainingLessonSummary {
  id: string;
  title: string;
  description: string | null;
  position: number;
  required: boolean;
  estimated_minutes: number | null;
  completed: boolean;
  content_locale: "uk" | "en";
  translation_fallback: boolean;
}

export interface EmployeeTrainingContentBlock {
  id: string;
  type: TrainingContentBlockType;
  position: number;
  payload: Record<string, unknown>;
  content_locale: "uk" | "en";
  translation_fallback: boolean;
}

export interface EmployeeTrainingHomeResponse {
  assignment: EmployeeTrainingAssignmentSummary | null;
  training: EmployeeTrainingSummary | null;
  modules: EmployeeTrainingModuleSummary[];
  progress: TrainingProgressResponse | null;
  next_action: EmployeeTrainingNextAction;
  content_locale: "uk" | "en";
  translation_fallback: boolean;
}

export interface EmployeeTrainingModuleDetail extends EmployeeTrainingModuleSummary {
  lessons: EmployeeTrainingLessonSummary[];
}

export interface EmployeeTrainingLessonDetail extends EmployeeTrainingLessonSummary {
  content_blocks: EmployeeTrainingContentBlock[];
}

export interface LessonCompletionSummary {
  id: string;
  assignment_id: string;
  lesson_id: string;
  lesson_version_id: string;
  completion_source: "employee" | "rollout_preserved" | "reassignment_preserved";
  completed_at: string;
}

export interface LessonCompletionResponse {
  completion: LessonCompletionSummary;
  assignment: EmployeeTrainingAssignmentSummary;
  progress: TrainingProgressResponse;
  next_action: EmployeeTrainingNextAction;
}

export interface EmployeeTrainingAssetAccessResponse {
  url: string;
  expires_in: 300;
}
