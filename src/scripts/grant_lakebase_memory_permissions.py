"""Grant Lakebase Postgres permissions to a Databricks App service principal.

Best-practice deployment usage:
    1) Deploy or update your app.
    2) Resolve the app service principal from app name.
    3) Grant schema/table/sequence privileges for the selected memory type.

Usage:
        # Preferred: resolve SP from app name (uses Databricks CLI profile)
        uv run python scripts/grant_lakebase_memory_permissions.py \
            --app-name multiagent-app-dev \
            --profile DEFAULT \
            --memory-type langgraph \
            --instance-name <lakebase-instance>

        # Backward compatible: pass SP client ID directly
        uv run python scripts/grant_lakebase_memory_permissions.py \
            <sp-client-id> \
            --memory-type openai \
            --project <project> --branch <branch>

        # Preview grants without applying
        uv run python scripts/grant_lakebase_memory_permissions.py \
            --app-name multiagent-app-dev \
            --memory-type langgraph \
            --instance-name <lakebase-instance> \
            --dry-run
"""

import argparse
import json
import os
import re
import subprocess
import sys

from dotenv import load_dotenv

load_dotenv()

DEFAULT_PROFILE = os.getenv("DATABRICKS_CONFIG_PROFILE", "DEFAULT")

# Schema used for memory tables. Defaults to "public" for backward compatibility.
# Set LAKEBASE_AGENT_MEMORY_SCHEMA to use a custom schema (for example, "agent_memory").
MEMORY_SCHEMA = os.getenv("LAKEBASE_AGENT_MEMORY_SCHEMA", "public")

# Per-memory-type schema-to-table definitions.
MEMORY_TYPE_SCHEMAS: dict[str, dict[str, list[str]]] = {
    "langgraph": {
        MEMORY_SCHEMA: [
            "checkpoint_migrations",
            "checkpoint_writes",
            "checkpoints",
            "checkpoint_blobs",
            "store_migrations",
            "store",
            "store_vectors",
            "vector_migrations",
        ],
        "backend": [
            "responses",
            "messages",
        ],
    },
    "openai": {
        MEMORY_SCHEMA: [
            "agent_sessions",
            "agent_messages",
        ],
        "backend": [
            "responses",
            "messages",
        ],
    },
}

# Memory types that require sequence privileges (auto-increment columns).
NEEDS_SEQUENCES = {
    "openai": [MEMORY_SCHEMA, "backend"],
    "langgraph": ["backend"],
}

# Shared schemas that require sequence privileges for all memory types.
# Drizzle uses __drizzle_migrations with an id SERIAL PRIMARY KEY column,
# which requires USAGE, SELECT, and UPDATE on the backing sequence.
SHARED_SEQUENCE_SCHEMAS = ["drizzle"]

# Shared schemas granted for all memory types (chat UI persistence).
SHARED_SCHEMAS: dict[str, list[str]] = {
    "ai_chatbot": ["Chat", "Message", "User", "Vote"],
    "drizzle": ["__drizzle_migrations"],
}


def _grant_permissions(client, grantee: str, memory_type: str):
    """Grant all permissions for the given memory type to the grantee role.

    Args:
        client: Active Lakebase client.
        grantee: Service principal client ID.
        memory_type: Memory type key (langgraph or openai).
    """
    from databricks_ai_bridge.lakebase import (
        SchemaPrivilege,
        SequencePrivilege,
        TablePrivilege,
    )

    # Build schema-to-table map.
    schema_tables: dict[str, list[str]] = dict(SHARED_SCHEMAS)
    for schema, tables in MEMORY_TYPE_SCHEMAS[memory_type].items():
        schema_tables.setdefault(schema, []).extend(tables)

    schema_privileges = [SchemaPrivilege.USAGE, SchemaPrivilege.CREATE]
    table_privileges = [
        TablePrivilege.SELECT,
        TablePrivilege.INSERT,
        TablePrivilege.UPDATE,
        TablePrivilege.DELETE,
    ]

    for schema, tables in schema_tables.items():
        print(f"Granting schema privileges on '{schema}'...")
        try:
            client.grant_schema(grantee=grantee, schemas=[schema], privileges=schema_privileges)
        except Exception as e:
            print(f"  Warning: schema grant failed (may not exist yet): {e}")

        qualified_tables = [f"{schema}.{t}" for t in tables]
        print(f"  Granting table privileges on {qualified_tables}...")
        try:
            client.grant_table(
                grantee=grantee, tables=qualified_tables, privileges=table_privileges
            )
        except Exception as e:
            print(f"  Warning: table grant failed (may not exist yet): {e}")

    # Grant sequence privileges for auto-increment columns.
    seq_schemas = list(SHARED_SEQUENCE_SCHEMAS)
    if memory_type in NEEDS_SEQUENCES:
        seq_schemas.extend(NEEDS_SEQUENCES[memory_type])
    seq_schemas = sorted(set(seq_schemas))

    for schema in seq_schemas:
        print(f"Granting sequence privileges on '{schema}' schema...")
        try:
            client.grant_all_sequences_in_schema(
                grantee=grantee,
                schemas=[schema],
                privileges=[
                    SequencePrivilege.USAGE,
                    SequencePrivilege.SELECT,
                    SequencePrivilege.UPDATE,
                ],
            )
        except Exception as e:
            print(f"  Warning: sequence grant failed (may not exist yet): {e}")

    print(
        "\nPermission grants complete. If some grants failed because tables don't "
        "exist yet, that is expected on a fresh branch; they will be created on first "
        "agent usage. Re-run this script after the first run to grant remaining permissions."
    )


def _parse_project_branch_from_endpoint(endpoint: str) -> tuple[str | None, str | None]:
    """Extract project and branch from an autoscaling endpoint path.

    Args:
        endpoint: Autoscaling endpoint path.

    Returns:
        Tuple of project and branch names; each may be None.
    """
    match = re.search(r"projects/([^/]+)/branches/([^/]+)", endpoint)
    if not match:
        return None, None
    return match.group(1), match.group(2)


def _resolve_sp_client_id(sp_client_id: str | None, app_name: str | None, profile: str) -> str:
    """Resolve app service principal client ID from explicit value or app name.

    Args:
        sp_client_id: Explicit service principal client ID.
        app_name: Databricks App name used for lookup.
        profile: Databricks CLI profile for lookup.

    Returns:
        Resolved service principal client ID.
    """
    if sp_client_id:
        return sp_client_id

    if not app_name:
        raise ValueError("Provide either <sp-client-id> positional argument or --app-name.")

    cmd = [
        "databricks",
        "apps",
        "get",
        app_name,
        "--output",
        "json",
        "--profile",
        profile,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise RuntimeError(
            f"Failed to resolve app service principal from app '{app_name}': {stderr}"
        )

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Could not parse JSON from `databricks apps get` output.") from exc

    resolved = payload.get("service_principal_client_id")
    if not resolved:
        raise RuntimeError(f"App '{app_name}' did not return service_principal_client_id.")
    return resolved


def _resolve_target(
    instance_name: str | None,
    autoscaling_endpoint: str | None,
    project: str | None,
    branch: str | None,
) -> tuple[str | None, str | None, str | None, str]:
    """Resolve exactly one Lakebase target.

    Args:
        instance_name: Provisioned Lakebase instance name.
        autoscaling_endpoint: Autoscaling endpoint path.
        project: Autoscaling project name.
        branch: Autoscaling branch name.

    Returns:
        Tuple of instance name, project, branch, and target mode.
    """
    has_provisioned = bool(instance_name)

    if autoscaling_endpoint and (not project or not branch):
        parsed_project, parsed_branch = _parse_project_branch_from_endpoint(autoscaling_endpoint)
        project = project or parsed_project
        branch = branch or parsed_branch

    has_autoscaling = bool(project and branch)

    if has_provisioned and has_autoscaling:
        raise ValueError(
            "Provide either provisioned (--instance-name) or autoscaling (--project/--branch), not both."
        )
    if not has_provisioned and not has_autoscaling:
        raise ValueError(
            "Lakebase connection is required. Provide --instance-name, --autoscaling-endpoint, "
            "or --project with --branch."
        )

    mode = "provisioned" if has_provisioned else "autoscaling"
    return instance_name, project, branch, mode


def _print_plan(
    grantee: str,
    memory_type: str,
    mode: str,
    instance_name: str | None,
    project: str | None,
    branch: str | None,
) -> None:
    """Print a human-readable summary of planned grants.

    Args:
        grantee: Service principal client ID.
        memory_type: Memory type key.
        mode: Target mode (provisioned or autoscaling).
        instance_name: Provisioned instance name when applicable.
        project: Autoscaling project name when applicable.
        branch: Autoscaling branch name when applicable.
    """
    print("Grant plan")
    print("-" * 40)
    print(f"Grantee: {grantee}")
    print(f"Memory type: {memory_type}")
    if mode == "provisioned":
        print(f"Lakebase target: provisioned instance '{instance_name}'")
    else:
        print(f"Lakebase target: autoscaling project '{project}', branch '{branch}'")
    print("Schemas: shared + memory-type specific")
    print(
        "Privileges: schema USAGE/CREATE, table SELECT/INSERT/UPDATE/DELETE, sequence USAGE/SELECT/UPDATE"
    )


def main():
    """Parse arguments, resolve targets, and apply Lakebase grants."""
    parser = argparse.ArgumentParser(
        description="Grant Lakebase permissions to an app service principal."
    )
    parser.add_argument(
        "sp_client_id",
        nargs="?",
        help="Service principal client ID (UUID). Optional when --app-name is provided.",
    )
    parser.add_argument(
        "--app-name",
        help="Databricks app name to resolve service_principal_client_id from.",
    )
    parser.add_argument(
        "--profile",
        default=DEFAULT_PROFILE,
        help="Databricks CLI profile to use when resolving --app-name (default: DATABRICKS_CONFIG_PROFILE or DEFAULT).",
    )
    parser.add_argument(
        "--memory-type",
        required=True,
        choices=list(MEMORY_TYPE_SCHEMAS.keys()),
        help="Memory type to grant permissions for",
    )
    parser.add_argument(
        "--instance-name",
        default=os.getenv("LAKEBASE_INSTANCE_NAME"),
        help="Lakebase instance name for provisioned instances (default: LAKEBASE_INSTANCE_NAME from .env)",
    )
    parser.add_argument(
        "--autoscaling-endpoint",
        default=os.getenv("LAKEBASE_AUTOSCALING_ENDPOINT"),
        help="Lakebase autoscaling endpoint path (default: LAKEBASE_AUTOSCALING_ENDPOINT from .env). "
        "e.g. projects/<project>/branches/<branch>/endpoints/primary",
    )
    parser.add_argument(
        "--project",
        default=os.getenv("LAKEBASE_AUTOSCALING_PROJECT"),
        help="Lakebase autoscaling project name (default: LAKEBASE_AUTOSCALING_PROJECT from .env)",
    )
    parser.add_argument(
        "--branch",
        default=os.getenv("LAKEBASE_AUTOSCALING_BRANCH"),
        help="Lakebase autoscaling branch name (default: LAKEBASE_AUTOSCALING_BRANCH from .env)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show grant plan without applying permissions.",
    )
    args = parser.parse_args()

    try:
        grantee = _resolve_sp_client_id(args.sp_client_id, args.app_name, args.profile)
        instance_name, project, branch, mode = _resolve_target(
            args.instance_name,
            args.autoscaling_endpoint,
            args.project,
            args.branch,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    # Ensure SDKs and downstream clients use the selected profile.
    os.environ["DATABRICKS_CONFIG_PROFILE"] = args.profile

    _print_plan(grantee, args.memory_type, mode, instance_name, project, branch)
    if args.dry_run:
        print("\nDry run requested; no grants were applied.")
        return

    from databricks_ai_bridge.lakebase import LakebaseClient

    with LakebaseClient(
        instance_name=instance_name or None,
        project=project or None,
        branch=branch or None,
    ) as client:
        if mode == "provisioned":
            print(f"Using provisioned instance: {instance_name}")
        else:
            print(f"Using autoscaling project: {project}, branch: {branch}")
        print(f"Memory type: {args.memory_type}")

        print(f"Creating role for SP {grantee}...")
        try:
            client.create_role(grantee, "SERVICE_PRINCIPAL")
            print("  Role created.")
        except Exception as e:
            if "already exists" in str(e).lower():
                print("  Role already exists, skipping.")
            else:
                raise

        _grant_permissions(client, grantee, args.memory_type)


if __name__ == "__main__":
    main()
