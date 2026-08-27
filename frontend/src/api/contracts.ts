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
