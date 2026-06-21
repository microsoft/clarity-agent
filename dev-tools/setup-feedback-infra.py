#!/usr/bin/env python3
"""
Setup and verify Azure infrastructure for Clarity feedback.

Creates (or verifies) the Azure resources needed to receive user feedback:

  1. Resource group
  2. Storage account + blob container (public access off)
  3. Function app (consumption plan, Python 3.11, managed identity)
  4. Custom write-only RBAC role for the function identity
  5. Role assignment scoped to the feedback container
  6. Optional reader role for a specified Azure AD group
  7. Permission audit — flags unexpected access on the container
  8. Function code deployment
  9. Function URL retrieval

Idempotent: safe to run repeatedly.  Each step checks whether the
resource already exists and is correctly configured.  In apply mode
it fixes any issues; in ``--verify-only`` mode it shows the exact
commands that would be run.

Prerequisites:
  - Azure CLI (``az``) installed and on PATH
  - Logged in (``az login``)
  - Sufficient permissions to create resources and role definitions

Usage:
    python dev-tools/setup-feedback-infra.py
    python dev-tools/setup-feedback-infra.py --verify-only
    python dev-tools/setup-feedback-infra.py --reader-group "Feedback Readers"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CUSTOM_ROLE_NAME = "Clarity Feedback Writer"
CUSTOM_ROLE_DESCRIPTION = (
    "Write-only access to blob storage for Clarity feedback submissions. "
    "Cannot read, list, or delete blobs."
)
CUSTOM_ROLE_DATA_ACTIONS = [
    "Microsoft.Storage/storageAccounts/blobServices/containers/blobs/write",
    "Microsoft.Storage/storageAccounts/blobServices/containers/blobs/add/action",
]

# Built-in roles that grant blob data-plane access.  Used by the
# permission audit to flag unexpected access.
_DATA_PLANE_ROLES = {
    "Storage Blob Data Owner",
    "Storage Blob Data Contributor",
    "Storage Blob Data Reader",
    "Storage Blob Delegator",
}


# ---------------------------------------------------------------------------
# Mode flag — set once from CLI args, read by _apply / _apply_json.
# ---------------------------------------------------------------------------

_verify_only: bool = False
_has_issues: bool = False


# ---------------------------------------------------------------------------
# Low-level helpers (always execute — used for reads)
# ---------------------------------------------------------------------------


def _run(
    cmd: list[str],
    *,
    check: bool = True,
    quiet: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run a shell command and return the result."""
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf8")
    if check and result.returncode != 0:
        stderr = result.stderr.strip()
        if not quiet:
            _error(f"Command failed: {shlex.join(cmd)}")
            for line in stderr.splitlines()[:10]:
                print(f"         {line}")
        raise SystemExit(1)
    return result


def _az_json(args: list[str], *, check: bool = True) -> object:
    """Run ``az ... -o json`` and parse the output."""
    result = _run(["az", *args, "-o", "json"], check=check, quiet=not check)
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        return result.stdout.strip()


def _az_show(args: list[str]) -> object | None:
    """Run an ``az ... show`` command; return parsed JSON or None."""
    result = _run(["az", *args, "-o", "json"], check=False, quiet=True)
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Apply helpers (respect _verify_only)
# ---------------------------------------------------------------------------


def _apply(label: str, cmd: list[str], *, verb: str = "CREATE") -> None:
    """Execute a state-changing shell command, or print it.

    In apply mode: logs and runs the command.
    In verify-only mode: logs the issue and prints the command.
    """
    global _has_issues
    _has_issues = True
    if _verify_only:
        _fixable(label)
        print(f"           To fix, run: {shlex.join(cmd)}")
        return
    (_create if verb == "CREATE" else _update)(label)
    _run(cmd)


def _apply_json(
    label: str,
    az_args: list[str],
    *,
    verb: str = "CREATE",
) -> object | None:
    """Execute a state-changing ``az`` command and return JSON, or print it.

    In apply mode: logs, runs, and returns parsed JSON.
    In verify-only mode: prints the command and returns ``None``.
    """
    global _has_issues
    _has_issues = True
    cmd = ["az", *az_args, "-o", "json"]
    if _verify_only:
        _fixable(label)
        print(f"           To fix, run: {shlex.join(cmd)}")
        return None
    (_create if verb == "CREATE" else _update)(label)
    return _az_json(az_args)


# ---------------------------------------------------------------------------
# Status output
# ---------------------------------------------------------------------------

_C = "\033["


def _ok(msg: str) -> None:
    print(f"  {_C}32m[OK]{_C}0m       {msg}")


def _create(msg: str) -> None:
    print(f"  {_C}33m[CREATE]{_C}0m   {msg}")


def _update(msg: str) -> None:
    print(f"  {_C}33m[UPDATE]{_C}0m   {msg}")


def _fixable(msg: str) -> None:
    print(f"  {_C}33m[FIXABLE]{_C}0m  {msg}")


def _error(msg: str) -> None:
    print(f"  {_C}31m[ERROR]{_C}0m    {msg}")


def _info(msg: str) -> None:
    print(f"  {_C}34m[INFO]{_C}0m     {msg}")


def _warn(msg: str) -> None:
    print(f"  {_C}33m[WARN]{_C}0m     {msg}")


# ---------------------------------------------------------------------------
# Scope helpers
# ---------------------------------------------------------------------------


def _container_scope(
    sub_id: str,
    rg: str,
    account: str,
    container: str,
) -> str:
    """Build the ARM resource ID for a blob container."""
    return (
        f"/subscriptions/{sub_id}/resourceGroups/{rg}"
        f"/providers/Microsoft.Storage/storageAccounts/{account}"
        f"/blobServices/default/containers/{container}"
    )


# ---------------------------------------------------------------------------
# Step 0: Prerequisites
# ---------------------------------------------------------------------------


def check_prerequisites() -> str:
    """Verify ``az`` is available and user is logged in.

    Returns the current subscription ID.
    """
    if not shutil.which("az"):
        _error("Azure CLI (az) is not installed or not on PATH.")
        _info("Install: https://learn.microsoft.com/en-us/cli/azure/install-azure-cli")
        raise SystemExit(1)

    account = _az_show(["account", "show"])
    if account is None or not isinstance(account, dict):
        _error("Not logged in to Azure. Run: az login")
        raise SystemExit(1)

    sub_id: str = account["id"]
    name: str = account.get("name", "unknown")
    _ok(f"Azure CLI authenticated (subscription: {name} [{sub_id[:8]}...])")
    return sub_id


# ---------------------------------------------------------------------------
# Step 1: Resource group
# ---------------------------------------------------------------------------


def ensure_resource_group(name: str, location: str) -> None:
    existing = _az_show(["group", "show", "--name", name])
    if existing is not None:
        _ok(f"Resource group '{name}' exists")
        return
    _apply_json(
        f"Resource group '{name}' in {location}",
        ["group", "create", "--name", name, "--location", location],
    )


# ---------------------------------------------------------------------------
# Step 2: Storage account
# ---------------------------------------------------------------------------


def ensure_storage_account(name: str, rg: str, location: str) -> None:
    existing = _az_show(
        [
            "storage",
            "account",
            "show",
            "--name",
            name,
            "--resource-group",
            rg,
        ]
    )
    if existing is not None:
        _ok(f"Storage account '{name}' exists")
        return
    _apply_json(
        f"Storage account '{name}' (Standard_LRS)",
        [
            "storage",
            "account",
            "create",
            "--name",
            name,
            "--resource-group",
            rg,
            "--location",
            location,
            "--sku",
            "Standard_LRS",
            "--kind",
            "StorageV2",
            "--min-tls-version",
            "TLS1_2",
            "--allow-blob-public-access",
            "false",
        ],
    )


# ---------------------------------------------------------------------------
# Step 3: Blob container
# ---------------------------------------------------------------------------


def _get_connection_string(account: str, rg: str) -> str | None:
    """Get storage connection string, or None if the account isn't accessible."""
    result = _az_json(
        [
            "storage",
            "account",
            "show-connection-string",
            "--name",
            account,
            "--resource-group",
            rg,
        ],
        check=False,
    )
    if isinstance(result, dict):
        return result.get("connectionString")
    return None


def ensure_storage_container(container: str, account: str, rg: str) -> None:
    conn_str = _get_connection_string(account, rg)
    if conn_str is None:
        _warn(f"Cannot verify container — storage account '{account}' not accessible")
        return

    result = _run(
        [
            "az",
            "storage",
            "container",
            "show",
            "--name",
            container,
            "--connection-string",
            conn_str,
            "-o",
            "json",
        ],
        check=False,
        quiet=True,
    )

    if result.returncode == 0:
        data = json.loads(result.stdout)
        props = data.get("properties", {})
        public = props.get("publicAccess")
        if public and public != "None":
            _apply(
                f"Container '{container}' — disable public access",
                [
                    "az",
                    "storage",
                    "container",
                    "set-permission",
                    "--name",
                    container,
                    "--connection-string",
                    conn_str,
                    "--public-access",
                    "off",
                ],
                verb="UPDATE",
            )
        else:
            _ok(f"Container '{container}' exists (public access off)")
        return

    _apply(
        f"Container '{container}' (public access off)",
        [
            "az",
            "storage",
            "container",
            "create",
            "--name",
            container,
            "--connection-string",
            conn_str,
            "--public-access",
            "off",
        ],
    )


# ---------------------------------------------------------------------------
# Step 4: Function app
# ---------------------------------------------------------------------------


def ensure_function_app(
    name: str,
    rg: str,
    storage_account: str,
    location: str,
) -> None:
    existing = _az_show(
        [
            "functionapp",
            "show",
            "--name",
            name,
            "--resource-group",
            rg,
        ]
    )
    if existing is not None:
        _ok(f"Function app '{name}' exists")
        return
    _apply_json(
        f"Function app '{name}' (Python 3.11, consumption plan)",
        [
            "functionapp",
            "create",
            "--name",
            name,
            "--resource-group",
            rg,
            "--storage-account",
            storage_account,
            "--consumption-plan-location",
            location,
            "--runtime",
            "python",
            "--runtime-version",
            "3.11",
            "--functions-version",
            "4",
            "--os-type",
            "Linux",
        ],
    )


# ---------------------------------------------------------------------------
# Step 5: Managed identity
# ---------------------------------------------------------------------------


def ensure_managed_identity(name: str, rg: str) -> str | None:
    """Ensure the function app has a system-assigned managed identity.

    Returns the identity's principal ID, or ``None`` if the function
    app doesn't exist yet (verify-only mode).
    """
    app = _az_show(["functionapp", "show", "--name", name, "--resource-group", rg])
    if app is None or not isinstance(app, dict):
        _warn(f"Cannot verify managed identity — function app '{name}' not accessible")
        return None

    identity = app.get("identity") or {}
    id_type = identity.get("type", "")

    if "SystemAssigned" in id_type and identity.get("principalId"):
        _ok(f"Managed identity enabled (principal: {identity['principalId'][:8]}...)")
        return identity["principalId"]

    result = _apply_json(
        "Enabling system-assigned managed identity",
        ["functionapp", "identity", "assign", "--name", name, "--resource-group", rg],
        verb="UPDATE",
    )
    if isinstance(result, dict) and result.get("principalId"):
        return result["principalId"]
    return None


# ---------------------------------------------------------------------------
# Step 6: Custom write-only RBAC role
# ---------------------------------------------------------------------------


def ensure_custom_role(sub_id: str) -> None:
    """Ensure the custom write-only role exists with correct permissions."""
    existing = _az_json(
        ["role", "definition", "list", "--name", CUSTOM_ROLE_NAME],
        check=False,
    )

    role_def = {
        "Name": CUSTOM_ROLE_NAME,
        "Description": CUSTOM_ROLE_DESCRIPTION,
        "Actions": [],
        "DataActions": CUSTOM_ROLE_DATA_ACTIONS,
        "NotDataActions": [],
        "AssignableScopes": [f"/subscriptions/{sub_id}"],
    }

    if isinstance(existing, list) and len(existing) > 0:
        role = existing[0]
        perms = role.get("permissions", [{}])[0]
        data_actions = set(perms.get("dataActions", []))
        expected = set(CUSTOM_ROLE_DATA_ACTIONS)
        not_data_actions = set(perms.get("notDataActions", []))
        actions = set(perms.get("actions", []))

        if data_actions == expected and not actions and not not_data_actions:
            _ok(f"Custom role '{CUSTOM_ROLE_NAME}' has correct permissions")
            return

        _apply_json(
            f"Custom role '{CUSTOM_ROLE_NAME}' — fix permissions",
            ["role", "definition", "update", "--role-definition", json.dumps(role_def)],
            verb="UPDATE",
        )
        return

    _apply_json(
        f"Custom role '{CUSTOM_ROLE_NAME}'",
        ["role", "definition", "create", "--role-definition", json.dumps(role_def)],
    )


# ---------------------------------------------------------------------------
# Step 7: Role assignments
# ---------------------------------------------------------------------------


def ensure_role_assignment(
    principal_id: str,
    role_name: str,
    scope: str,
    label: str,
) -> None:
    """Ensure *principal_id* has *role_name* at *scope*."""
    existing = _az_json(
        [
            "role",
            "assignment",
            "list",
            "--assignee",
            principal_id,
            "--role",
            role_name,
            "--scope",
            scope,
        ],
        check=False,
    )

    if isinstance(existing, list) and len(existing) > 0:
        _ok(f"Role '{role_name}' assigned to {label}")
        return

    _apply_json(
        f"Role assignment: '{role_name}' -> {label}",
        [
            "role",
            "assignment",
            "create",
            "--assignee",
            principal_id,
            "--role",
            role_name,
            "--scope",
            scope,
        ],
    )


def ensure_reader_group(group_name: str, scope: str) -> None:
    """Ensure an Azure AD group has reader access on the container."""
    group = _az_show(["ad", "group", "show", "--group", group_name])
    if group is None or not isinstance(group, dict):
        _warn(f"Azure AD group '{group_name}' not found — cannot assign reader role")
        return

    principal_id: str = group["id"]
    ensure_role_assignment(
        principal_id,
        "Storage Blob Data Reader",
        scope,
        f"group '{group_name}'",
    )


# ---------------------------------------------------------------------------
# Step 8: Permission audit
# ---------------------------------------------------------------------------


def audit_container_permissions(
    scope: str,
    *,
    function_principal_id: str | None,
    reader_group: str | None,
) -> None:
    """List data-plane role assignments on the container and warn about
    any that are unexpected.
    """
    assignments = _az_json(
        [
            "role",
            "assignment",
            "list",
            "--scope",
            scope,
            "--include-inherited",
        ],
        check=False,
    )

    if not isinstance(assignments, list):
        _warn("Could not list role assignments for audit")
        return

    # Resolve reader group principal ID if specified.
    reader_principal: str | None = None
    if reader_group:
        group = _az_show(["ad", "group", "show", "--group", reader_group])
        if isinstance(group, dict):
            reader_principal = group.get("id")

    expected_principals: set[str] = set()
    if function_principal_id:
        expected_principals.add(function_principal_id)
    if reader_principal:
        expected_principals.add(reader_principal)

    unexpected: list[str] = []
    for a in assignments:
        role = a.get("roleDefinitionName", "")
        principal = a.get("principalId", "")
        principal_name = a.get("principalName", principal)

        # Only audit data-plane roles (blob access).
        if role not in _DATA_PLANE_ROLES and role != CUSTOM_ROLE_NAME:
            continue

        if principal in expected_principals:
            continue

        unexpected.append(f"{role} -> {principal_name} (scope: {a.get('scope', '?')})")

    if unexpected:
        _warn(f"Unexpected data-plane role assignments on the container ({len(unexpected)}):")
        for line in unexpected:
            print(f"           {line}")
    else:
        _ok("No unexpected data-plane access on container")


# ---------------------------------------------------------------------------
# Step 9: Function app settings
# ---------------------------------------------------------------------------


def ensure_function_settings(
    name: str,
    rg: str,
    account: str,
    container: str,
) -> None:
    """Ensure the function app has the correct application settings."""
    result = _az_json(
        [
            "functionapp",
            "config",
            "appsettings",
            "list",
            "--name",
            name,
            "--resource-group",
            rg,
        ],
        check=False,
    )

    if not isinstance(result, list):
        _warn(f"Cannot verify settings — function app '{name}' not accessible")
        return

    settings = {s["name"]: s["value"] for s in result if "name" in s}
    needs_update = (
        settings.get("FEEDBACK_STORAGE_ACCOUNT") != account
        or settings.get("FEEDBACK_CONTAINER") != container
    )

    if not needs_update:
        _ok("Function app settings are correct")
        return

    _apply_json(
        "Function app settings (FEEDBACK_STORAGE_ACCOUNT, FEEDBACK_CONTAINER)",
        [
            "functionapp",
            "config",
            "appsettings",
            "set",
            "--name",
            name,
            "--resource-group",
            rg,
            "--settings",
            f"FEEDBACK_STORAGE_ACCOUNT={account}",
            f"FEEDBACK_CONTAINER={container}",
        ],
        verb="UPDATE",
    )


# ---------------------------------------------------------------------------
# Step 10: Deploy function code
# ---------------------------------------------------------------------------


def deploy_function(name: str, rg: str, function_dir: Path) -> None:
    """Deploy function code if the local source has changed.

    Builds a zip of the function directory, hashes the zip, and
    compares against a ``FEEDBACK_CODE_HASH`` app setting stored
    after each successful deployment.
    """
    # Build the zip and hash it in one pass.
    with tempfile.NamedTemporaryFile(suffix=".zip") as tmp:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in sorted(function_dir.rglob("*")):
                if file_path.is_file() and "__pycache__" not in file_path.parts:
                    zf.write(file_path, file_path.relative_to(function_dir))

        tmp.seek(0)
        local_hash = hashlib.sha256(tmp.read()).hexdigest()[:16]

        # Read the deployed hash from app settings.
        result = _az_json(
            [
                "functionapp",
                "config",
                "appsettings",
                "list",
                "--name",
                name,
                "--resource-group",
                rg,
            ],
            check=False,
        )

        deployed_hash: str | None = None
        if isinstance(result, list):
            settings = {s["name"]: s["value"] for s in result if "name" in s}
            deployed_hash = settings.get("FEEDBACK_CODE_HASH")

        if deployed_hash == local_hash:
            _ok(f"Function code is current ({local_hash})")
            return

        detail = (
            f"local {local_hash} vs deployed {deployed_hash}"
            if deployed_hash
            else f"local {local_hash}, no deployed hash"
        )

        if _verify_only:
            global _has_issues
            _has_issues = True
            _fixable(f"Function code is outdated ({detail})")
            _info("To fix, run this script without --verify-only")
            return

        _update(f"Deploying function code ({detail})")
        _run(
            [
                "az",
                "functionapp",
                "deployment",
                "source",
                "config-zip",
                "--name",
                name,
                "--resource-group",
                rg,
                "--src",
                tmp.name,
                "--build-remote",
                "true",
            ]
        )

        # Record the hash so the next run can detect changes.
        _run(
            [
                "az",
                "functionapp",
                "config",
                "appsettings",
                "set",
                "--name",
                name,
                "--resource-group",
                rg,
                "--settings",
                f"FEEDBACK_CODE_HASH={local_hash}",
                "-o",
                "json",
            ]
        )
        _ok(f"Function code deployed ({local_hash})")


# ---------------------------------------------------------------------------
# Step 11: Function URL
# ---------------------------------------------------------------------------


def get_function_url(name: str, rg: str) -> str | None:
    keys = _az_show(
        [
            "functionapp",
            "function",
            "keys",
            "list",
            "--name",
            name,
            "--resource-group",
            rg,
            "--function-name",
            "submit_feedback",
        ]
    )
    if keys is None or not isinstance(keys, dict):
        _warn(
            "Could not retrieve function keys — the function may not "
            "be deployed yet.  Re-run after deployment."
        )
        return None

    func_key = keys.get("default")
    if not func_key:
        _warn("No 'default' function key found")
        return None

    return f"https://{name}.azurewebsites.net/api/feedback?code={func_key}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    global _verify_only

    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent
    function_dir = repo_root / "infra" / "feedback-function"

    parser = argparse.ArgumentParser(
        description="Setup and verify Azure infrastructure for Clarity feedback.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help=(
            "Check existing infrastructure without creating or "
            "modifying anything.  Shows the exact commands that "
            "would fix each issue.  Exits non-zero if anything is wrong."
        ),
    )
    parser.add_argument(
        "--resource-group",
        default="clarity-feedback",
        help="Azure resource group name (default: clarity-feedback).",
    )
    parser.add_argument(
        "--storage-account",
        default="clarityfeedback",
        help=(
            "Azure storage account name — must be globally unique, "
            "3-24 chars, lowercase alphanumeric only "
            "(default: clarityfeedback)."
        ),
    )
    parser.add_argument(
        "--function-app",
        default="clarity-feedback",
        help="Azure Function app name — must be globally unique (default: clarity-feedback).",
    )
    parser.add_argument(
        "--container",
        default="feedback",
        help="Blob container name (default: feedback).",
    )
    parser.add_argument(
        "--location",
        default="westus2",
        help="Azure region (default: westus2).",
    )
    parser.add_argument(
        "--reader-group",
        default=None,
        help=(
            "Azure AD group to grant read access on the feedback "
            "container (e.g. 'Feedback Readers').  Optional."
        ),
    )

    args = parser.parse_args()
    _verify_only = args.verify_only

    mode = "VERIFY" if _verify_only else "SETUP"
    print(f"\n  Clarity Feedback Infrastructure — {mode}")
    print(f"  Resource group:  {args.resource_group}")
    print(f"  Storage account: {args.storage_account}")
    print(f"  Function app:    {args.function_app}")
    print(f"  Container:       {args.container}")
    print(f"  Location:        {args.location}")
    if args.reader_group:
        print(f"  Reader group:    {args.reader_group}")
    print()

    # 0. Prerequisites
    sub_id = check_prerequisites()

    # 1. Resource group
    ensure_resource_group(args.resource_group, args.location)

    # 2. Storage account
    ensure_storage_account(
        args.storage_account,
        args.resource_group,
        args.location,
    )

    # 3. Blob container (with public access verification)
    ensure_storage_container(
        args.container,
        args.storage_account,
        args.resource_group,
    )

    # 4. Function app
    ensure_function_app(
        args.function_app,
        args.resource_group,
        args.storage_account,
        args.location,
    )

    # 5. Managed identity
    principal_id = ensure_managed_identity(
        args.function_app,
        args.resource_group,
    )

    # 6. Custom write-only RBAC role
    ensure_custom_role(sub_id)

    # 7. Role assignments
    scope = _container_scope(
        sub_id,
        args.resource_group,
        args.storage_account,
        args.container,
    )
    if principal_id is not None:
        ensure_role_assignment(
            principal_id,
            CUSTOM_ROLE_NAME,
            scope,
            f"function app '{args.function_app}'",
        )
    else:
        _warn("Cannot verify role assignment — managed identity not yet provisioned")

    if args.reader_group:
        ensure_reader_group(args.reader_group, scope)

    # 8. Permission audit
    audit_container_permissions(
        scope,
        function_principal_id=principal_id,
        reader_group=args.reader_group,
    )

    # 9. Function app settings
    ensure_function_settings(
        args.function_app,
        args.resource_group,
        args.storage_account,
        args.container,
    )

    # 10. Deploy
    if not function_dir.exists():
        _error(f"Function source not found at {function_dir}")
        raise SystemExit(1)
    deploy_function(args.function_app, args.resource_group, function_dir)

    # 11. Retrieve function URL
    print()
    url = get_function_url(args.function_app, args.resource_group)
    if url:
        _ok("Function URL retrieved")
        print()
        print("  Set this in src/clarity_agent/feedback.py:")
        print(f'    FEEDBACK_URL = "{url}"')
    print()

    if _verify_only and _has_issues:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
