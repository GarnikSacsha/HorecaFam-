import argparse
import asyncio
import getpass
import sys
import warnings
from collections.abc import Callable
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, EmailStr, TypeAdapter
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.email import normalize_email
from app.db.session import create_engine, create_session_factory
from app.models import AdminAccess, AuditEvent, Organization, User
from app.security.passwords import PasswordManager


class ProvisioningError(ValueError):
    pass


class ProvisionResult(BaseModel):
    status: Literal["planned", "created", "existing"]
    user_id: UUID | None = None
    access_id: UUID | None = None


async def verify_target(
    db: AsyncSession,
    *,
    settings: Settings,
    environment: str,
    host: str,
    database: str,
    database_user: str,
) -> None:
    url = make_url(settings.database_url)
    if (
        settings.app_env not in {"test", "staging"}
        or environment != settings.app_env
        or url.host != host
        or url.database != database
        or url.username != database_user
    ):
        raise ProvisioningError("Provisioning target confirmation does not match")
    row = (await db.execute(text("SELECT current_database(), current_user"))).one()
    if row[0] != database or row[1] != database_user:
        raise ProvisioningError("Connected database identity does not match")
    revisions = list(await db.scalars(text("SELECT version_num FROM alembic_version")))
    if revisions != ["0019_auth_security_budgets"]:
        raise ProvisioningError("Provisioning requires the reviewed migration revision")


def read_password() -> str:
    # Забороняємо getpass переходити до видимого stdin без захищеного термінала.
    if not sys.stdin.isatty():
        raise ProvisioningError("A private interactive terminal is required")
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        password = getpass.getpass("New password (hidden): ")
        confirmed = getpass.getpass("Confirm password (hidden): ")
    if password != confirmed or not 8 <= len(password) <= 128:
        raise ProvisioningError("Passwords must match and contain 8 to 128 characters")
    return password


async def run(arguments: argparse.Namespace) -> ProvisionResult:
    settings = get_settings()
    engine = create_engine(settings)
    try:
        async with create_session_factory(engine)() as db, db.begin():
            await verify_target(
                db,
                settings=settings,
                environment=arguments.confirm_environment,
                host=arguments.expected_host,
                database=arguments.expected_database,
                database_user=arguments.expected_db_user,
            )
            if arguments.operation == "initial-operator":
                return await provision_operator(
                    db, email=arguments.email, apply=arguments.apply, password_reader=read_password
                )
            return await provision_admin(
                db,
                email=arguments.email,
                operator_email=arguments.operator_email,
                organization_id=arguments.organization_id,
                apply=arguments.apply,
                reuse_existing=arguments.reuse_existing,
                password_reader=read_password,
            )
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Guarded one-time staging access provisioning")
    parser.add_argument("operation", choices=["initial-operator", "organization-admin"])
    parser.add_argument("--email", required=True)
    parser.add_argument("--operator-email")
    parser.add_argument("--organization-id", type=UUID)
    parser.add_argument("--reuse-existing", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-environment", required=True, choices=["test", "staging"])
    parser.add_argument("--expected-host", required=True)
    parser.add_argument("--expected-database", required=True)
    parser.add_argument("--expected-db-user", required=True)
    arguments = parser.parse_args()
    if arguments.operation == "organization-admin" and (
        not arguments.operator_email or arguments.organization_id is None
    ):
        parser.error("organization-admin requires --operator-email and --organization-id")
    if arguments.operation == "initial-operator" and (
        arguments.operator_email or arguments.organization_id or arguments.reuse_existing
    ):
        parser.error("initial-operator does not accept organization or reuse options")
    try:
        result = asyncio.run(run(arguments))
    except (Exception, KeyboardInterrupt):
        # Помилки SQL/валідації можуть містити пароль, хеш або URL; не друкуємо їх.
        print(
            "Provisioning failed; inspect target and account state before retrying.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
    print(result.model_dump_json())


async def provision_admin(
    db: AsyncSession,
    *,
    email: str,
    operator_email: str,
    organization_id: UUID,
    apply: bool,
    reuse_existing: bool,
    password_reader: Callable[[], str],
) -> ProvisionResult:
    email = normalize_email(str(TypeAdapter(EmailStr).validate_python(email)))
    operator_email = normalize_email(str(TypeAdapter(EmailStr).validate_python(operator_email)))
    if email == operator_email:
        raise ProvisioningError("Technical operator and organization administrator must differ")
    if apply:
        await db.execute(text("SELECT pg_advisory_xact_lock(17120260911)"))
    operator_access = await db.scalar(
        select(AdminAccess)
        .join(User, User.id == AdminAccess.user_id)
        .where(
            User.email_normalized == operator_email,
            AdminAccess.scope == "platform_operator",
            AdminAccess.status == "active",
        )
        .with_for_update()
    )
    organization = await db.scalar(
        select(Organization).where(Organization.id == organization_id).with_for_update()
    )
    if operator_access is None or organization is None or organization.status != "active":
        raise ProvisioningError("An active operator and exact active organization are required")
    user = await db.scalar(select(User).where(User.email_normalized == email).with_for_update())
    if user is not None:
        accesses = list(await db.scalars(select(AdminAccess).where(AdminAccess.user_id == user.id)))
        if any(access.scope == "platform_operator" for access in accesses):
            raise ProvisioningError("The target identity has platform access history")
        matching = [access for access in accesses if access.organization_id == organization_id]
        if matching:
            if len(matching) == 1 and matching[0].status == "active" and user.password_hash:
                return ProvisionResult(status="existing", user_id=user.id, access_id=matching[0].id)
            raise ProvisioningError("Target organization access requires separate recovery review")
        if not reuse_existing or not user.password_hash:
            raise ProvisioningError("Existing identity requires explicit reuse and a password")
    if not apply:
        return ProvisionResult(status="planned", user_id=user.id if user else None)
    if user is None:
        password = password_reader()
        if not 8 <= len(password) <= 128:
            raise ProvisioningError("Password must contain 8 to 128 characters")
        user = User(
            email_normalized=email,
            password_hash=await PasswordManager().hash_async(password),
            preferred_locale="uk",
        )
        db.add(user)
        await db.flush()
    access = AdminAccess(
        user_id=user.id,
        scope="organization_admin",
        organization_id=organization_id,
        status="active",
        granted_by_user_id=operator_access.user_id,
    )
    db.add(access)
    await db.flush()
    db.add(
        AuditEvent(
            organization_id=organization_id,
            actor_user_id=operator_access.user_id,
            actor_type="user",
            action="organization_admin_provisioned",
            target_type="user",
            target_id=user.id,
            request_id=uuid4(),
            outcome="success",
        )
    )
    await db.flush()
    return ProvisionResult(status="created", user_id=user.id, access_id=access.id)


async def provision_operator(
    db: AsyncSession, *, email: str, apply: bool, password_reader: Callable[[], str]
) -> ProvisionResult:
    email = normalize_email(str(TypeAdapter(EmailStr).validate_python(email)))
    # Єдиний замок серіалізує початкове надання доступу без нової таблиці стану.
    if apply:
        await db.execute(text("SELECT pg_advisory_xact_lock(17120260911)"))
    user = await db.scalar(select(User).where(User.email_normalized == email).with_for_update())
    accesses = list(
        await db.scalars(select(AdminAccess).where(AdminAccess.scope == "platform_operator"))
    )
    if accesses:
        if (
            len(accesses) == 1
            and user is not None
            and user.password_hash is not None
            and accesses[0].user_id == user.id
            and accesses[0].status == "active"
        ):
            return ProvisionResult(status="existing", user_id=user.id, access_id=accesses[0].id)
        raise ProvisioningError("Initial operator state conflicts with requested setup")
    if user is not None:
        raise ProvisioningError("Initial operator identity already exists without platform access")
    if not apply:
        return ProvisionResult(status="planned")
    password = password_reader()
    if not 8 <= len(password) <= 128:
        raise ProvisioningError("Password must contain 8 to 128 characters")
    user = User(
        email_normalized=email,
        password_hash=await PasswordManager().hash_async(password),
        preferred_locale="uk",
    )
    db.add(user)
    await db.flush()
    access = AdminAccess(user_id=user.id, scope="platform_operator", status="active")
    db.add(access)
    await db.flush()
    db.add(
        AuditEvent(
            actor_type="system",
            action="initial_operator_created",
            target_type="user",
            target_id=user.id,
            request_id=uuid4(),
            outcome="success",
        )
    )
    await db.flush()
    return ProvisionResult(status="created", user_id=user.id, access_id=access.id)


if __name__ == "__main__":
    main()
