import { useEffect, useState } from "react";

import type { ApiClient } from "../api/client";
import type { EmployeeListResponse, EmployeeSummary, LocationSummary } from "../api/contracts";

export interface OrganizationDirectory {
  employees: EmployeeSummary[];
  employeeName: (employeeId: string) => string;
  locationName: (locationId: string) => string;
}

export function employeeDisplayName(employee: EmployeeSummary): string {
  const fullName = [employee.first_name, employee.last_name].filter(Boolean).join(" ");
  return fullName || employee.email;
}

/**
 * Display-only names for employees and locations. A failed lookup never blocks the page:
 * callers fall back to neutral labels instead of exposing identifiers.
 */
export function useOrganizationDirectory(
  client: ApiClient,
  organizationId: string | undefined,
): OrganizationDirectory {
  const [employees, setEmployees] = useState<EmployeeSummary[]>([]);
  const [locations, setLocations] = useState<LocationSummary[]>([]);

  useEffect(() => {
    if (!organizationId) return;
    let active = true;
    const safe = <T>(path: string) =>
      Promise.resolve()
        .then(() => client.request<T>(path))
        .catch(() => null);
    void Promise.all([
      safe<EmployeeListResponse>(`/organizations/${organizationId}/employees`),
      safe<LocationSummary[]>(`/organizations/${organizationId}/locations`),
    ]).then(([employeeResponse, locationResponse]) => {
      if (!active) return;
      setEmployees(employeeResponse?.items ?? []);
      setLocations(Array.isArray(locationResponse) ? locationResponse : []);
    });
    return () => {
      active = false;
    };
  }, [client, organizationId]);

  return {
    employees,
    employeeName: (employeeId) => {
      const employee = employees.find((item) => item.id === employeeId);
      return employee ? employeeDisplayName(employee) : "Працівник";
    },
    locationName: (locationId) =>
      locations.find((item) => item.id === locationId)?.name ?? "Локація",
  };
}
