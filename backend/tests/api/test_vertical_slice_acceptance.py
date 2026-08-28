from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import AuthorizationContext, require_active_employee
from app.core.config import Settings
from app.models import (
    ApiIdempotencyRecord,
    AuditEvent,
    BackgroundJob,
    EmailDelivery,
    EmployeeProfile,
    Invitation,
    OrganizationMembership,
    Session,
)
from app.security.invitation_tokens import InvitationTokenManager
from app.security.mfa import MfaSecretCipher, TotpVerifier
from app.security.passwords import PasswordManager
from app.security.tokens import hash_secret
from app.services.applicability import (
    ActivationApplicabilityResult,
    evaluate_activation_applicability,
)
from app.services.invitation_delivery import (
    EmailAdapterResult,
    InvitationEmailMessage,
    deliver_invitation_email,
)
from tests.factories.auth import make_admin_access, make_mfa_credential
from tests.factories.identity import (
    make_location,
    make_membership,
    make_organization,
    make_role,
    make_user,
)

FIXED_NOW = datetime(2030, 8, 27, 15, 0, tzinfo=UTC)
TOTP_SECRET = b"01234567890123456789"
ADMIN_PASSWORD = "stage7-admin-password"
EMPLOYEE_PASSWORD = "stage7-employee-password"


class CapturingEmailAdapter:
    def __init__(self) -> None:
        self.messages: list[InvitationEmailMessage] = []

    async def send_invitation(self, message: InvitationEmailMessage) -> EmailAdapterResult:
        self.messages.append(message)
        return EmailAdapterResult(provider="fake", provider_message_id="stage7-message-1")


def add_active_employee_probe(app: FastAPI) -> None:
    @app.get("/api/v1/test/stage7/organizations/{organization_id}/employee")
    async def active_employee_probe(
        organization_id: UUID,
        authorization: Annotated[AuthorizationContext, Depends(require_active_employee)],
    ) -> dict[str, str]:
        return {
            "organization_id": str(organization_id),
            "user_id": str(authorization.user.id),
        }


async def test_complete_backend_slice_from_admin_login_to_active_employee_access(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    auth_settings: Settings,
    db_session: AsyncSession,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW
    add_active_employee_probe(auth_app)
    organization = make_organization(name="Stage 7 acceptance organization")
    admin = make_user(
        email_normalized="stage7-admin@example.com",
        password_hash=PasswordManager().hash(ADMIN_PASSWORD),
    )
    role = make_role(organization)
    location = make_location(organization)
    db_session.add_all([organization, admin, role, location])
    await db_session.flush()
    cipher = MfaSecretCipher([key.get_secret_value() for key in auth_settings.mfa_encryption_keys])
    db_session.add_all(
        [
            make_admin_access(
                admin,
                scope="organization_admin",
                organization=organization,
            ),
            make_mfa_credential(
                admin,
                secret_encrypted=cipher.encrypt(TOTP_SECRET),
                confirmed_at=FIXED_NOW - timedelta(days=1),
            ),
        ]
    )
    await db_session.commit()
    organization_id = organization.id
    admin_id = admin.id
    role_id = role.id
    location_id = location.id

    async with AsyncClient(
        transport=ASGITransport(app=auth_app),
        base_url="https://api.test",
    ) as admin_client:
        login = await admin_client.post(
            "/api/v1/auth/login",
            json={"email": admin.email_normalized, "password": ADMIN_PASSWORD},
        )
        assert login.status_code == 202
        assert login.json()["status"] == "mfa_required"
        assert "horeca_mfa_challenge" in admin_client.cookies
        assert "horeca_session" not in admin_client.cookies

        mfa = await admin_client.post(
            "/api/v1/auth/mfa/verify",
            json={"code": TotpVerifier().generate(TOTP_SECRET, FIXED_NOW)},
        )
        assert mfa.status_code == 200
        assert mfa.json()["session"]["mfa_verified"] is True
        assert mfa.json()["organization_access"] == [
            {
                "organization_id": str(organization_id),
                "membership_status": None,
                "is_employee": False,
                "is_organization_admin": True,
            }
        ]
        assert "horeca_session" in admin_client.cookies
        assert "horeca_mfa_challenge" not in admin_client.cookies
        admin_csrf = mfa.json()["csrf_token"]

        invitation_response = await admin_client.post(
            f"/api/v1/organizations/{organization_id}/invitations",
            headers={
                "Origin": "https://frontend.test",
                "X-CSRF-Token": admin_csrf,
                "Idempotency-Key": "stage7-create-invitation",
            },
            json={"email": " Stage7.Employee@Example.COM "},
        )
        assert invitation_response.status_code == 201
        assert set(invitation_response.json()) == {
            "id",
            "organization_id",
            "email",
            "status",
            "expires_at",
            "created_at",
            "updated_at",
        }
        assert invitation_response.json()["organization_id"] == str(organization_id)
        assert invitation_response.json()["email"] == "stage7.employee@example.com"
        assert invitation_response.json()["status"] == "pending"
        invitation_id = UUID(invitation_response.json()["id"])

        db_session.expire_all()
        invitation = await db_session.get_one(Invitation, invitation_id)
        job = await db_session.scalar(
            select(BackgroundJob)
            .join(EmailDelivery, EmailDelivery.job_id == BackgroundJob.id)
            .where(EmailDelivery.invitation_id == invitation_id)
        )
        assert job is not None and job.status == "pending"
        delivery = await db_session.scalar(
            select(EmailDelivery).where(EmailDelivery.invitation_id == invitation_id)
        )
        assert delivery is not None and delivery.status == "pending"
        adapter = CapturingEmailAdapter()
        delivered = await deliver_invitation_email(
            db_session,
            job_id=job.id,
            token_manager=InvitationTokenManager(auth_settings.invitation_token_hmac_keys),
            adapter=adapter,
            now=FIXED_NOW,
        )
        await db_session.commit()
        assert delivered is True
        assert len(adapter.messages) == 1
        message = adapter.messages[0]
        assert message.invitation_id == invitation_id
        assert message.organization_id == organization_id
        assert message.email == "stage7.employee@example.com"
        assert message.token not in invitation_response.text
        assert message.token not in str(job.payload)
        assert message.token not in invitation.token_hash
        assert invitation.token_hash == hash_secret(message.token)
        assert job.status == "completed"
        assert delivery.status == "accepted"

        accepted = await auth_client.post(
            "/api/v1/invitations/accept",
            json={
                "token": message.token,
                "acceptance_mode": "activate_access",
                "password": EMPLOYEE_PASSWORD,
            },
        )
        assert accepted.status_code == 201
        accepted_body = accepted.json()
        assert accepted_body["status"] == "accepted"
        assert accepted_body["acceptance_mode"] == "activate_access"
        assert accepted_body["user"]["email"] == "stage7.employee@example.com"
        assert accepted_body["session"]["mfa_verified"] is False
        assert accepted_body["membership"]["organization_id"] == str(organization_id)
        assert accepted_body["membership"]["status"] == "pending"
        assert message.token not in accepted.text
        assert EMPLOYEE_PASSWORD not in accepted.text
        employee_id = UUID(accepted_body["membership"]["employee_profile_id"])
        employee_user_id = UUID(accepted_body["user"]["id"])

        denied_pending = await auth_client.get(
            f"/api/v1/test/stage7/organizations/{organization_id}/employee"
        )
        assert denied_pending.status_code == 403
        assert denied_pending.json()["code"] == "FORBIDDEN"

        listed = await admin_client.get(
            f"/api/v1/organizations/{organization_id}/employees",
            params={"status": "pending", "query": "stage7.employee@example.com"},
        )
        assert listed.status_code == 200
        assert [item["id"] for item in listed.json()["items"]] == [str(employee_id)]

        updated = await admin_client.patch(
            f"/api/v1/organizations/{organization_id}/employees/{employee_id}",
            headers={
                "Origin": "https://frontend.test",
                "X-CSRF-Token": admin_csrf,
            },
            json={
                "first_name": "Марія",
                "last_name": "Іваненко",
                "operational_role_id": str(role_id),
                "location_id": str(location_id),
            },
        )
        assert updated.status_code == 200
        assert updated.json()["membership_status"] == "pending"
        assert updated.json()["profile_complete"] is True

        db_session.expire_all()
        session_count_before_activation = await db_session.scalar(
            select(func.count()).select_from(Session)
        )
        activation_headers = {
            "Origin": "https://frontend.test",
            "X-CSRF-Token": admin_csrf,
            "Idempotency-Key": "stage7-activate-employee",
        }
        activated = await admin_client.post(
            f"/api/v1/organizations/{organization_id}/employees/{employee_id}/activate",
            headers=activation_headers,
        )
        replayed = await admin_client.post(
            f"/api/v1/organizations/{organization_id}/employees/{employee_id}/activate",
            headers=activation_headers,
        )
        expected_activation = {
            "employee_id": str(employee_id),
            "organization_id": str(organization_id),
            "membership_status": "active",
            "training_participation_status": "active",
            "activated_at": FIXED_NOW.isoformat().replace("+00:00", "Z"),
        }
        assert activated.status_code == 200
        assert activated.json() == expected_activation
        assert "set-cookie" not in activated.headers
        assert replayed.status_code == 200
        assert replayed.json() == expected_activation
        assert "set-cookie" not in replayed.headers

    active_access = await auth_client.get(
        f"/api/v1/test/stage7/organizations/{organization_id}/employee"
    )
    assert active_access.status_code == 200
    assert active_access.json() == {
        "organization_id": str(organization_id),
        "user_id": str(employee_user_id),
    }
    session_context = await auth_client.get("/api/v1/auth/session")
    assert session_context.status_code == 200
    assert session_context.json()["organization_access"][0]["membership_status"] == "active"
    own_profile = await auth_client.get("/api/v1/me/profile")
    assert own_profile.status_code == 200
    assert own_profile.json()["profiles"][0]["id"] == str(employee_id)
    assert own_profile.json()["profiles"][0]["membership_status"] == "active"

    db_session.expire_all()
    membership = await db_session.scalar(
        select(OrganizationMembership)
        .join(EmployeeProfile, EmployeeProfile.membership_id == OrganizationMembership.id)
        .where(EmployeeProfile.id == employee_id)
    )
    assert membership is not None
    assert membership.status == "active"
    assert membership.activated_at == FIXED_NOW
    assert await db_session.scalar(select(func.count()).select_from(Session)) == (
        session_count_before_activation
    )
    idempotency_records = list(
        (
            await db_session.scalars(
                select(ApiIdempotencyRecord).where(
                    ApiIdempotencyRecord.organization_id == organization_id
                )
            )
        ).all()
    )
    assert {(record.action, record.key) for record in idempotency_records} == {
        ("employee.activate", "stage7-activate-employee"),
        ("invitation.create", "stage7-create-invitation"),
    }
    audit_actions = list(
        (
            await db_session.scalars(
                select(AuditEvent.action).where(AuditEvent.organization_id == organization_id)
            )
        ).all()
    )
    for expected_action in (
        "invitation_created",
        "invitation_accepted",
        "employee_profile_updated",
        "employee_activated",
    ):
        assert audit_actions.count(expected_action) == 1
    activation_audit = await db_session.scalar(
        select(AuditEvent).where(
            AuditEvent.organization_id == organization_id,
            AuditEvent.action == "employee_activated",
        )
    )
    assert activation_audit is not None
    assert activation_audit.actor_user_id == admin_id
    assert activation_audit.target_id == employee_id
    assert activation_audit.old_values == {"membership_status": "pending"}
    assert activation_audit.new_values == {
        "membership_status": "active",
        "training_applicability_effects": ["not_applicable"],
        "assignment_count": 0,
        "notification_count": 0,
    }
    assert "Марія" not in str(activation_audit.old_values)
    assert "Марія" not in str(activation_audit.new_values)
    assert await evaluate_activation_applicability(
        db_session,
        organization_id=organization_id,
        employee_profile_id=employee_id,
    ) == ActivationApplicabilityResult(
        published_content_count=0,
        assignment_count=0,
        notification_count=0,
        effects=("not_applicable",),
    )


async def test_disabled_employee_is_denied_by_active_employee_guard(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW
    add_active_employee_probe(auth_app)
    organization = make_organization(name="Disabled Stage 7 boundary")
    user = make_user(email_normalized="stage7-disabled@example.com")
    membership = make_membership(
        organization,
        user,
        status="disabled",
        activated_at=None,
        disabled_at=FIXED_NOW - timedelta(days=1),
    )
    profile = EmployeeProfile(
        membership=membership,
        organization_id=organization.id,
        first_name="Disabled",
        last_name="Employee",
    )
    raw_session = "stage7-disabled-session"
    db_session.add_all([organization, user, membership, profile])
    await db_session.flush()
    db_session.add(
        Session(
            user_id=user.id,
            token_hash=hash_secret(raw_session),
            csrf_token_hash=hash_secret("stage7-disabled-csrf"),
            last_seen_at=FIXED_NOW,
            absolute_expires_at=FIXED_NOW + timedelta(days=30),
        )
    )
    await db_session.commit()
    auth_client.cookies.set("horeca_session", raw_session, path="/api/v1")

    denied = await auth_client.get(f"/api/v1/test/stage7/organizations/{organization.id}/employee")

    assert denied.status_code == 403
    assert denied.json()["code"] == "FORBIDDEN"
