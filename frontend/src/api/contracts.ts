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
