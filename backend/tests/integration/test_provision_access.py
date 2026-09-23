import asyncio
import logging
import os
import subprocess
import sys
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from httpx import AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.session import create_engine, create_session_factory
from app.models import AdminAccess, AuditEvent, User
from app.operations.provision_access import (
    ProvisioningError,
    provision_admin,
    provision_operator,
    verify_target,
)
from app.security.passwords import PasswordManager
from tests.factories.identity import make_organization, make_user

BACKEND_ROOT = Path(__file__).resolve().parents[2]


@pytest_asyncio.fixture
async def reviewed_provisioning_database(
    db_session: AsyncSession, test_database_settings: Settings
) -> AsyncIterator[None]:
    # Одноразовий CLI перевіряємо на справжній погодженій схемі, не підмінюючи її номер.
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", test_database_settings.database_url)
    logger = logging.getLogger("app.errors")
    was_disabled = logger.disabled
    await db_session.rollback()
    try:
        await asyncio.to_thread(command.downgrade, config, "0019_auth_security_budgets")
        yield
    finally:
        await db_session.rollback()
        try:
            await asyncio.to_thread(command.upgrade, config, "head")
        finally:
            logger.disabled = was_disabled


@pytest.mark.integration
async def test_initial_operator_is_atomic_replay_safe_and_not_email_verified(
    db_session: AsyncSession,
) -> None:
    calls: list[bool] = []

    def password() -> str:
        calls.append(True)
        return "Synthetic-operator-123"

    planned = await provision_operator(
        db_session, email="operator@example.com", apply=False, password_reader=password
    )
    assert planned.status == "planned"
    assert calls == []
    assert await db_session.scalar(select(func.count()).select_from(User)) == 0
    created = await provision_operator(
        db_session, email="operator@example.com", apply=True, password_reader=password
    )
    await db_session.commit()
    assert created.status == "created"
    user = await db_session.get(User, created.user_id)
    assert user is not None and user.password_hash is not None
    assert PasswordManager().verify(user.password_hash, "Synthetic-operator-123")
    assert user.email_verified_at is None
    access = await db_session.get(AdminAccess, created.access_id)
    assert access is not None and access.scope == "platform_operator"
    assert access.organization_id is None
    replay = await provision_operator(
        db_session, email="operator@example.com", apply=True, password_reader=password
    )
    assert replay == created.model_copy(update={"status": "existing"})
    assert calls == [True]
    assert await db_session.scalar(select(func.count()).select_from(User)) == 1
    assert await db_session.scalar(select(func.count()).select_from(AuditEvent)) == 1


@pytest.mark.integration
async def test_admin_is_separate_and_replays_without_password_prompt(
    db_session: AsyncSession,
) -> None:
    operator = await provision_operator(
        db_session,
        email="operator@example.com",
        apply=True,
        password_reader=lambda: "Synthetic-operator-123",
    )
    organization = make_organization()
    db_session.add(organization)
    await db_session.commit()
    calls: list[bool] = []

    def password() -> str:
        calls.append(True)
        return "Synthetic-admin-123"

    result = await provision_admin(
        db_session,
        email="admin@example.com",
        operator_email="operator@example.com",
        organization_id=organization.id,
        apply=True,
        reuse_existing=False,
        password_reader=password,
    )
    await db_session.commit()
    assert result.status == "created"
    assert result.user_id != operator.user_id
    access = await db_session.get(AdminAccess, result.access_id)
    assert access is not None and access.scope == "organization_admin"
    assert access.organization_id == organization.id
    assert access.granted_by_user_id == operator.user_id
    replay = await provision_admin(
        db_session,
        email="admin@example.com",
        operator_email="operator@example.com",
        organization_id=organization.id,
        apply=True,
        reuse_existing=False,
        password_reader=password,
    )
    assert replay == result.model_copy(update={"status": "existing"})
    assert calls == [True]
    assert await db_session.scalar(select(func.count()).select_from(AdminAccess)) == 2


@pytest.mark.integration
async def test_provisioning_refuses_production_even_when_confirmation_matches(
    db_session: AsyncSession,
) -> None:
    with pytest.raises(ProvisioningError):
        await verify_target(
            db_session,
            settings=Settings(
                app_env="production", database_url="postgresql+asyncpg://example.invalid/production"
            ),
            environment="production",
            host="example.invalid",
            database="production",
            database_user="runtime",
        )


@pytest.mark.integration
@pytest.mark.usefixtures("reviewed_provisioning_database")
async def test_target_matches_real_database_and_rejects_revision_and_identity(
    db_session: AsyncSession,
    test_database_settings: Settings,
) -> None:
    url = make_url(test_database_settings.database_url)
    assert url.host and url.database and url.username

    async def check(**changes: str) -> None:
        values = dict(
            environment="test",
            host=str(url.host),
            database=str(url.database),
            database_user=str(url.username),
        )
        values.update(changes)
        await verify_target(db_session, settings=test_database_settings, **values)

    await check()
    for key in ("environment", "host", "database", "database_user"):
        with pytest.raises(ProvisioningError):
            await check(**{key: "wrong"})
    await db_session.execute(text("UPDATE alembic_version SET version_num='unexpected'"))
    try:
        with pytest.raises(ProvisioningError):
            await check()
    finally:
        await db_session.rollback()


@pytest.mark.integration
async def test_current_head_is_not_implicitly_authorized_for_one_time_provisioning(
    db_session: AsyncSession, test_database_settings: Settings
) -> None:
    url = make_url(test_database_settings.database_url)
    revision = await db_session.scalar(text("SELECT version_num FROM alembic_version"))
    assert revision != "0019_auth_security_budgets"
    with pytest.raises(ProvisioningError, match="reviewed migration revision"):
        await verify_target(
            db_session,
            settings=test_database_settings,
            environment="test",
            host=str(url.host),
            database=str(url.database),
            database_user=str(url.username),
        )
    assert await db_session.scalar(select(func.count()).select_from(User)) == 0


@pytest.mark.integration
async def test_operator_collision_and_second_identity_are_denied(db_session: AsyncSession) -> None:
    existing = make_user(email_normalized="partial@example.com")
    db_session.add(existing)
    await db_session.commit()
    with pytest.raises(ProvisioningError):
        await provision_operator(
            db_session,
            email=existing.email_normalized,
            apply=True,
            password_reader=lambda: pytest.fail("No password prompt"),
        )
    await db_session.rollback()
    await provision_operator(
        db_session,
        email="operator@example.com",
        apply=True,
        password_reader=lambda: "Synthetic-operator-123",
    )
    await db_session.commit()
    with pytest.raises(ProvisioningError):
        await provision_operator(
            db_session,
            email="second@example.com",
            apply=True,
            password_reader=lambda: pytest.fail("No password prompt"),
        )


@pytest.mark.integration
async def test_admin_reuse_preserves_identity_and_refuses_revoked_access(
    db_session: AsyncSession,
) -> None:
    await provision_operator(
        db_session,
        email="operator@example.com",
        apply=True,
        password_reader=lambda: "Synthetic-operator-123",
    )
    organization = make_organization()
    user = make_user(email_normalized="existing@example.com", password_hash="unchanged-hash")
    db_session.add_all([organization, user])
    await db_session.commit()
    org_id, user_id = organization.id, user.id

    async def grant(reuse: bool, apply: bool = True) -> object:
        return await provision_admin(
            db_session,
            email="existing@example.com",
            operator_email="operator@example.com",
            organization_id=org_id,
            apply=apply,
            reuse_existing=reuse,
            password_reader=lambda: pytest.fail("Do not reset password"),
        )

    with pytest.raises(ProvisioningError):
        await grant(False)
    await db_session.rollback()
    await grant(True, False)
    assert await db_session.scalar(select(func.count()).select_from(AdminAccess)) == 1
    await grant(True)
    await db_session.commit()
    preserved = await db_session.get(User, user_id)
    assert preserved is not None and preserved.password_hash == "unchanged-hash"
    assert preserved.email_verified_at is None
    access = await db_session.scalar(select(AdminAccess).where(AdminAccess.user_id == user_id))
    assert access is not None
    access.status = "revoked"
    access.revoked_at = datetime.now(UTC)
    await db_session.commit()
    with pytest.raises(ProvisioningError):
        await grant(True)


@pytest.mark.integration
async def test_admin_wrong_operator_archived_org_and_platform_target_denied(
    db_session: AsyncSession,
) -> None:
    await provision_operator(
        db_session,
        email="operator@example.com",
        apply=True,
        password_reader=lambda: "Synthetic-operator-123",
    )
    organization = make_organization(status="archived")
    db_session.add(organization)
    await db_session.commit()
    org_id = organization.id
    for operator, target in (
        ("operator@example.com", "operator@example.com"),
        ("missing@example.com", "admin@example.com"),
        ("operator@example.com", "admin@example.com"),
    ):
        with pytest.raises(ProvisioningError):
            await provision_admin(
                db_session,
                email=target,
                operator_email=operator,
                organization_id=org_id,
                apply=True,
                reuse_existing=False,
                password_reader=lambda: pytest.fail("No password prompt"),
            )
        await db_session.rollback()
    assert await db_session.scalar(select(func.count()).select_from(User)) == 1


@pytest.mark.integration
async def test_operator_rollback_leaves_no_partial_identity(db_session: AsyncSession) -> None:
    await provision_operator(
        db_session,
        email="operator@example.com",
        apply=True,
        password_reader=lambda: "Synthetic-operator-123",
    )
    await db_session.rollback()
    for model in (User, AdminAccess, AuditEvent):
        assert await db_session.scalar(select(func.count()).select_from(model)) == 0


@pytest.mark.integration
async def test_concurrent_operator_apply_converges(
    db_session: AsyncSession,
    test_database_settings: Settings,
) -> None:
    engine = create_engine(test_database_settings)
    sessions = create_session_factory(engine)

    async def apply() -> str:
        async with sessions() as db, db.begin():
            result = await provision_operator(
                db,
                email="operator@example.com",
                apply=True,
                password_reader=lambda: "Synthetic-operator-123",
            )
            return result.status

    try:
        results = await asyncio.gather(apply(), apply())
    finally:
        await engine.dispose()
    assert sorted(results) == ["created", "existing"]
    assert await db_session.scalar(select(func.count()).select_from(User)) == 1


@pytest.mark.integration
@pytest.mark.usefixtures("reviewed_provisioning_database")
async def test_real_module_cli_dry_run(
    db_session: AsyncSession,
    test_database_settings: Settings,
) -> None:
    url = make_url(test_database_settings.database_url)
    environment = os.environ.copy()
    environment["APP_ENV"] = "test"
    environment["DATABASE_URL"] = test_database_settings.database_url
    result = await asyncio.to_thread(
        subprocess.run,
        [
            sys.executable,
            "-m",
            "app.operations.provision_access",
            "initial-operator",
            "--email",
            "operator@example.com",
            "--confirm-environment",
            "test",
            "--expected-host",
            str(url.host),
            "--expected-database",
            str(url.database),
            "--expected-db-user",
            str(url.username),
        ],
        capture_output=True,
        text=True,
        env=environment,
        timeout=30,
    )
    assert result.returncode == 0, "CLI dry-run failed"
    assert '"status":"planned"' in result.stdout
    assert await db_session.scalar(select(func.count()).select_from(User)) == 0


@pytest.mark.integration
async def test_provisioned_admin_login_requires_normal_mfa_enrollment(
    db_session: AsyncSession,
    auth_client: AsyncClient,
) -> None:
    await provision_operator(
        db_session,
        email="operator@example.com",
        apply=True,
        password_reader=lambda: "Synthetic-operator-123",
    )
    organization = make_organization()
    db_session.add(organization)
    await db_session.flush()
    result = await provision_admin(
        db_session,
        email="admin@example.com",
        operator_email="operator@example.com",
        organization_id=organization.id,
        apply=True,
        reuse_existing=False,
        password_reader=lambda: "Synthetic-admin-123",
    )
    await db_session.commit()
    response = await auth_client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com", "password": "Synthetic-admin-123"}
    )
    assert response.status_code == 202
    assert response.json()["status"] == "mfa_enrollment_required"
    assert "horeca_session" not in auth_client.cookies
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(AdminAccess)
            .where(AdminAccess.user_id == result.user_id, AdminAccess.scope == "platform_operator")
        )
        == 0
    )
