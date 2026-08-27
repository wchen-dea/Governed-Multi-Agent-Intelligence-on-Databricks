"""Grant post-deploy runtime permissions for a Databricks App service principal.

This script performs these actions:
1) Resolves app service principal client id from app name.
2) Discovers configured runtime resources for the selected target.
3) Checks underlying resource existence (Genie Agents, UC catalog/schema, AI Search,
   serving endpoints, SQL warehouse).
4) Grants required permissions to the app service principal:
   - Unity Catalog: SELECT ON ALL TABLES (catalog/schema USE grants are
     provisioned outside this pipeline)
    - Genie Agents: CAN_RUN
    - AI Search endpoints: CAN_USE
   - Serving endpoints: CAN_QUERY
   - SQL warehouse: CAN_USE

The script uses the Databricks CLI for all checks/grants.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

SUPPORTED_TARGETS = ("dev", "qa", "stg", "prd")


def _is_placeholder(value: str | None) -> bool:
    if not value:
        return True
    stripped = value.strip()
    return stripped.startswith("<") and stripped.endswith(">")


class CliError(RuntimeError):
    pass


class DatabricksCli:
    """Lightweight Databricks CLI runner with optional JSON decoding."""

    def __init__(self, profile: str):
        """Store CLI profile used for all Databricks commands.

        Args:
            profile: Databricks CLI profile name.
        """
        self.profile = profile

    def run(self, args: list[str], expect_json: bool = False, check: bool = True) -> Any:
        """Execute a Databricks CLI command.

        Args:
            args: Command arguments after the `databricks` executable.
            expect_json: When true, parse and return JSON output.
            check: When true, raise on non-zero exit code.

        Returns:
            A `subprocess.CompletedProcess` for non-JSON calls, parsed JSON
            content for JSON calls, or `None` for JSON calls that failed with
            `check=False`.

        Raises:
            CliError: If command execution fails with `check=True` or JSON
                decoding fails.
        """
        cmd = ["databricks", *args, "--profile", self.profile]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if check and result.returncode != 0:
            stderr = (result.stderr or "").strip()
            raise CliError(f"CLI failed: {' '.join(cmd)}\n{stderr}")
        if not expect_json:
            return result
        if result.returncode != 0:
            return None
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise CliError(f"Invalid JSON from CLI: {' '.join(cmd)}") from exc


class PermissionManager:
    """Resolve and grant runtime permissions for the app service principal.

    This manager discovers target-scoped resources, validates securables, and
    applies Databricks permissions plus Unity Catalog grants needed by runtime
    subagents.
    """

    def __init__(
        self, cli: DatabricksCli, target: str, app_name: str, dry_run: bool, fail_open: bool
    ):
        """Initialize permission management context.

        Args:
            cli: Databricks CLI wrapper.
            target: Deployment target (`dev`, `qa`, `stg`, or `prd`).
            app_name: Databricks app name used to resolve app principal.
            dry_run: If true, print planned actions without applying grants.
            fail_open: If true, return success even when some grants fail.
        """
        self.cli = cli
        self.target = target
        self.app_name = app_name
        self.dry_run = dry_run
        self.fail_open = fail_open
        self.failures: list[str] = []
        self._vector_endpoint_id_by_name: dict[str, str] | None = None
        self._serving_endpoint_id_by_name: dict[str, str] | None = None
        self._warehouse_id_by_name: dict[str, str] | None = None

    def _warn_or_fail(self, message: str) -> None:
        self.failures.append(message)
        print(f"WARN: {message}")

    def _read_target_vars(self) -> dict[str, Any]:
        target_file = Path("targets") / f"{self.target}.yml"
        if not target_file.exists():
            raise CliError(f"Target file not found: {target_file}")

        yaml = YAML(typ="safe")
        data = yaml.load(target_file.read_text(encoding="utf-8")) or {}
        try:
            return data["targets"][self.target].get("variables", {})
        except Exception as exc:
            raise CliError(f"Could not read variables from {target_file}") from exc

    def _read_subagent_resource_hints(
        self,
    ) -> tuple[list[str], list[str], list[tuple[str, str, str]], list[dict[str, str]]]:
        """Extract resource hints from target subagent configuration.

        Returns:
            A tuple of:
            - Genie Agent space ids.
            - Serving endpoint names.
            - AI Search MCP triples as `(catalog, schema, index)`.
            - Lakebase project configs as dicts with project_id, branch_id, endpoint_id keys.

        Raises:
            CliError: If the subagent file exists but contains invalid JSON.
        """
        config_file = Path("src/aiserver/domain") / f"subagents.{self.target}.json"
        if not config_file.exists():
            return [], [], [], []

        try:
            raw = json.loads(config_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CliError(f"Invalid JSON in {config_file}") from exc

        genie_space_ids: list[str] = []
        serving_endpoints: list[str] = []
        ai_search_indexes: list[tuple[str, str, str]] = []
        lakebase_configs: list[dict[str, str]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            kind = item.get("type")
            if kind == "genie":
                sid = item.get("space_id")
                if isinstance(sid, str) and sid.strip() and not _is_placeholder(sid):
                    genie_space_ids.append(sid.strip())
            elif kind in {"serving_endpoint", "app"}:
                endpoint = item.get("endpoint")
                if isinstance(endpoint, str) and endpoint.strip() and not _is_placeholder(endpoint):
                    serving_endpoints.append(endpoint.strip())
            elif kind == "mcp":
                mcp_url = item.get("mcp_url")
                if isinstance(mcp_url, str):
                    parsed = self._parse_ai_search_mcp_url(mcp_url)
                    if parsed is not None:
                        ai_search_indexes.append(parsed)
            elif kind == "lakebase":
                project_id = item.get("project_id", "")
                branch_id = item.get("branch_id", "")
                endpoint_id = item.get("endpoint_id", "")
                if project_id and branch_id and endpoint_id and not _is_placeholder(project_id):
                    lakebase_configs.append(
                        {
                            "project_id": project_id,
                            "branch_id": branch_id,
                            "endpoint_id": endpoint_id,
                        }
                    )

        return (
            sorted(set(genie_space_ids)),
            sorted(set(serving_endpoints)),
            sorted(set(ai_search_indexes)),
            lakebase_configs,
        )

    def _parse_ai_search_mcp_url(self, mcp_url: str) -> tuple[str, str, str] | None:
        """Parse an AI Search MCP URL into `(catalog, schema, index)`.

        Args:
            mcp_url: MCP route expected in `/api/2.0/mcp/vector-search/...` format.

        Returns:
            Parsed `(catalog, schema, index)` when valid and non-placeholder,
            otherwise `None`.
        """
        parts = [part for part in mcp_url.strip().split("/") if part]
        # Expected format:
        # /api/2.0/mcp/{vector-search|ai-search}/<catalog>/<schema>/<index>
        if len(parts) != 7:
            return None
        if (
            parts[0] != "api"
            or parts[1] != "2.0"
            or parts[2] != "mcp"
            or parts[3] not in {"vector-search", "ai-search"}
        ):
            return None

        catalog, schema, index_name = parts[4], parts[5], parts[6]
        if not catalog or not schema or not index_name:
            return None
        if _is_placeholder(catalog) or _is_placeholder(schema) or _is_placeholder(index_name):
            return None
        return (catalog, schema, index_name)

    def _resolve_app_sp_client_id(self) -> str:
        payload = self.cli.run(["apps", "get", self.app_name, "--output", "json"], expect_json=True)
        if not isinstance(payload, dict):
            raise CliError(f"Could not fetch app details for {self.app_name}")

        sp_client_id = payload.get("service_principal_client_id")
        if not isinstance(sp_client_id, str) or not sp_client_id.strip():
            raise CliError(
                f"App {self.app_name} did not return service_principal_client_id in `databricks apps get`"
            )
        return sp_client_id.strip()

    def _update_permissions(
        self, object_type: str, object_id: str, level: str, sp_client_id: str
    ) -> bool:
        payload = {
            "access_control_list": [
                {
                    "service_principal_name": sp_client_id,
                    "permission_level": level,
                }
            ]
        }
        args = [
            "permissions",
            "update",
            object_type,
            object_id,
            "--json",
            json.dumps(payload),
        ]
        if self.dry_run:
            print(f"DRY RUN: databricks {' '.join(args)}")
            return True

        result = self.cli.run(args, check=False)
        return result.returncode == 0

    def _list_vector_endpoint_ids(self) -> dict[str, str]:
        if self._vector_endpoint_id_by_name is not None:
            return self._vector_endpoint_id_by_name

        payload = self.cli.run(
            ["vector-search-endpoints", "list-endpoints", "--output", "json"],
            expect_json=True,
            check=False,
        )
        mapping: dict[str, str] = {}
        if isinstance(payload, list):
            for item in payload:
                if not isinstance(item, dict):
                    continue
                name = item.get("name")
                endpoint_id = item.get("id")
                if isinstance(name, str) and isinstance(endpoint_id, str) and name and endpoint_id:
                    mapping[name] = endpoint_id

        self._vector_endpoint_id_by_name = mapping
        return mapping

    def _list_serving_endpoint_ids(self) -> dict[str, str]:
        if self._serving_endpoint_id_by_name is not None:
            return self._serving_endpoint_id_by_name

        payload = self.cli.run(
            ["serving-endpoints", "list", "--output", "json"],
            expect_json=True,
            check=False,
        )
        mapping: dict[str, str] = {}
        if isinstance(payload, list):
            for item in payload:
                if not isinstance(item, dict):
                    continue
                name = item.get("name")
                endpoint_id = item.get("id")
                if isinstance(name, str) and isinstance(endpoint_id, str) and name and endpoint_id:
                    mapping[name] = endpoint_id

        self._serving_endpoint_id_by_name = mapping
        return mapping

    def _list_warehouse_ids(self) -> dict[str, str]:
        if self._warehouse_id_by_name is not None:
            return self._warehouse_id_by_name

        payload = self.cli.run(
            ["warehouses", "list", "--output", "json"], expect_json=True, check=False
        )
        mapping: dict[str, str] = {}
        if isinstance(payload, list):
            for item in payload:
                if not isinstance(item, dict):
                    continue
                name = item.get("name")
                warehouse_id = item.get("id")
                if (
                    isinstance(name, str)
                    and isinstance(warehouse_id, str)
                    and name
                    and warehouse_id
                ):
                    mapping[name] = warehouse_id

        self._warehouse_id_by_name = mapping
        return mapping

    def _resolve_serving_endpoint_id(self, endpoint: str) -> str | None:
        endpoints = self._list_serving_endpoint_ids()
        if endpoint in endpoints:
            return endpoints[endpoint]
        return None

    def _resolve_vector_endpoint_id(self, endpoint: str) -> str | None:
        endpoints = self._list_vector_endpoint_ids()
        if endpoint in endpoints:
            return endpoints[endpoint]
        return None

    def _resolve_warehouse_id(self, warehouse: str) -> str | None:
        # Already an id and exists.
        if self.cli.run(["warehouses", "get", warehouse], check=False).returncode == 0:
            return warehouse
        # Try resolving from configured warehouse name.
        return self._list_warehouse_ids().get(warehouse)

    def _execute_sql_grant(self, warehouse_id: str, statement: str) -> bool:
        payload = {
            "warehouse_id": warehouse_id,
            "statement": statement,
            "wait_timeout": "30s",
        }
        args = ["api", "post", "/api/2.0/sql/statements", "--json", json.dumps(payload)]
        if self.dry_run:
            print(f"DRY RUN SQL: {statement}")
            return True

        result = self.cli.run(args, expect_json=True, check=False)
        if not isinstance(result, dict):
            return False

        status = result.get("status") or {}
        state = status.get("state")
        if state not in {"SUCCEEDED", "PENDING", "RUNNING"}:
            error_message = (status.get("error") or {}).get("message")
            if error_message:
                print(f"  SQL error: {error_message}")
            return False
        return True


    def _grant_uc_privilege(
        self,
        securable_type: str,
        full_name: str,
        privilege: str,
        principal: str,
    ) -> bool:
        payload = {
            "changes": [
                {
                    "principal": principal,
                    "add": [privilege],
                }
            ]
        }
        args = [
            "grants",
            "update",
            securable_type,
            full_name,
            "--json",
            json.dumps(payload),
        ]
        if self.dry_run:
            print(f"DRY RUN: databricks {' '.join(args)}")
            return True

        result = self.cli.run(args, check=False)
        return result.returncode == 0

    def _uc_securable_exists(self, securable_type: str, full_name: str) -> bool:
        args = ["grants", "get", securable_type, full_name]
        result = self.cli.run(args, check=False)
        return result.returncode == 0

    def _check_ai_search_uc_securables(
        self,
        ai_search_indexes: list[tuple[str, str, str]],
    ) -> list[tuple[str, str, list[str]]]:
        if not ai_search_indexes:
            print("INFO: No AI Search MCP UC objects discovered from subagent config.")
            return []

        checked: list[tuple[str, str, list[str]]] = []
        print("Validating AI Search UC securables before grants...")
        for catalog, schema, index_name in ai_search_indexes:
            source_table = f"{index_name.replace('_index', '_index_writeback_table')}"
            tables = [index_name, source_table]

            cat_ok = self._uc_securable_exists("catalog", catalog)
            print(f"UC CHECK: {'OK' if cat_ok else 'MISSING'} -> catalog {catalog}")
            if not cat_ok:
                self._warn_or_fail(f"UC catalog not found or inaccessible: {catalog}")

            schema_full = f"{catalog}.{schema}"
            schema_ok = self._uc_securable_exists("schema", schema_full)
            print(f"UC CHECK: {'OK' if schema_ok else 'MISSING'} -> schema {schema_full}")
            if not schema_ok:
                self._warn_or_fail(f"UC schema not found or inaccessible: {schema_full}")

            existing_tables: list[str] = []
            for table in tables:
                table_full = f"{catalog}.{schema}.{table}"
                table_ok = self._uc_securable_exists("table", table_full)
                print(f"UC CHECK: {'OK' if table_ok else 'MISSING'} -> table {table_full}")
                if table_ok:
                    existing_tables.append(table)
                else:
                    self._warn_or_fail(f"UC table not found or inaccessible: {table_full}")

            if cat_ok and schema_ok and existing_tables:
                checked.append((catalog, schema, existing_tables))

        return checked

    def _grant_ai_search_uc_permissions(
        self,
        ai_search_securables: list[tuple[str, str, list[str]]],
        sp_client_id: str,
    ) -> None:
        """Grant UC privileges needed by AI Search-backed MCP tools.

        Args:
            ai_search_securables: Validated securables in
                `(catalog, schema, [tables...])` form.
            sp_client_id: App service principal client id.

        Side Effects:
            Applies `SELECT` grants through Databricks grants APIs. Catalog/schema
            `USE_CATALOG`/`USE_SCHEMA` access is provisioned outside this app's
            deploy pipeline and is not granted here.
        """
        if not ai_search_securables:
            print("INFO: No validated AI Search UC securables to grant.")
            return

        # Use the app service principal object id for Unity Catalog grants.
        principal = sp_client_id

        for catalog, schema, table_names in ai_search_securables:
            for table in table_names:
                table_full = f"{catalog}.{schema}.{table}"
                select_ok = self._grant_uc_privilege("table", table_full, "SELECT", principal)
                print(f"UC GRANT: {'OK' if select_ok else 'FAILED'} -> SELECT ON {table_full}")
                if not select_ok:
                    self._warn_or_fail(f"Failed UC grant SELECT on {table_full}")

    def _grant_uc_permissions(
        self,
        catalog: str | None,
        schema: str | None,
        warehouse_id_or_name: str | None,
        sp_client_id: str,
    ) -> None:
        if not catalog or not schema:
            print("INFO: Skipping UC grants; catalog/schema not configured for target.")
            return
        if _is_placeholder(catalog) or _is_placeholder(schema):
            print("INFO: Skipping UC grants; catalog/schema contains placeholder values.")
            return
        if not warehouse_id_or_name or _is_placeholder(warehouse_id_or_name):
            self._warn_or_fail("Cannot run UC grant SQL without a valid warehouse id.")
            return

        warehouse_id = self._resolve_warehouse_id(warehouse_id_or_name)
        if not warehouse_id:
            self._warn_or_fail(f"SQL warehouse not found or inaccessible: {warehouse_id_or_name}")
            return

        self._grant_warehouse_can_use(warehouse_id, sp_client_id)

        catalog_ok = self.cli.run(["catalogs", "get", catalog], check=False).returncode == 0
        schema_ok = (
            self.cli.run(["schemas", "get", f"{catalog}.{schema}"], check=False).returncode == 0
        )
        if not catalog_ok:
            self._warn_or_fail(f"Catalog not found or inaccessible: {catalog}")
            return
        if not schema_ok:
            self._warn_or_fail(f"Schema not found or inaccessible: {catalog}.{schema}")
            return

        # Catalog/schema `USE CATALOG`/`USE SCHEMA` access is provisioned outside
        # this app's deploy pipeline and is not granted here.
        # Unity Catalog has no "ALL TABLES IN SCHEMA" clause; schema-level SELECT/MODIFY
        # grants are inherited by all tables within the schema.
        principal = sp_client_id.replace("`", "")
        statements = [
            f"GRANT CREATE TABLE ON SCHEMA `{catalog}`.`{schema}` TO `{principal}`",
            f"GRANT SELECT ON SCHEMA `{catalog}`.`{schema}` TO `{principal}`",
            f"GRANT MODIFY ON SCHEMA `{catalog}`.`{schema}` TO `{principal}`",
        ]
        for stmt in statements:
            ok = self._execute_sql_grant(warehouse_id, stmt)
            print(f"UC GRANT: {'OK' if ok else 'FAILED'} -> {stmt}")
            if not ok:
                self._warn_or_fail(f"Failed UC SQL grant: {stmt}")

    def _grant_warehouse_can_use(self, warehouse_id: str, sp_client_id: str) -> None:
        ok = self._update_permissions("warehouses", warehouse_id, "CAN_USE", sp_client_id)
        print(f"WAREHOUSE PERMISSION: {'OK' if ok else 'FAILED'} -> {warehouse_id} CAN_USE")
        if not ok:
            self._warn_or_fail(f"Failed to grant warehouse CAN_USE: {warehouse_id}")

    def _grant_genie_can_run(self, genie_space_ids: list[str], sp_client_id: str) -> None:
        if not genie_space_ids:
            print("INFO: No Genie Agents configured for target.")
            return

        for space_id in genie_space_ids:
            if _is_placeholder(space_id):
                continue
            exists = self.cli.run(["genie", "get-space", space_id], check=False).returncode == 0
            if not exists:
                self._warn_or_fail(f"Genie Agent not found or inaccessible: {space_id}")
                continue

            ok = self._update_permissions("genie", space_id, "CAN_RUN", sp_client_id)
            print(f"GENIE PERMISSION: {'OK' if ok else 'FAILED'} -> {space_id} CAN_RUN")
            if not ok:
                self._warn_or_fail(f"Failed to grant Genie CAN_RUN: {space_id}")

    def _grant_serving_can_query(self, endpoint_names: list[str], sp_client_id: str) -> None:
        if not endpoint_names:
            print("INFO: No serving endpoints configured for target.")
            return

        for endpoint in endpoint_names:
            if _is_placeholder(endpoint):
                continue
            endpoint_id = self._resolve_serving_endpoint_id(endpoint)
            if not endpoint_id:
                self._warn_or_fail(f"Serving endpoint not found or inaccessible: {endpoint}")
                continue

            ok = self._update_permissions(
                "serving-endpoints", endpoint_id, "CAN_QUERY", sp_client_id
            )
            print(f"SERVING PERMISSION: {'OK' if ok else 'FAILED'} -> {endpoint} CAN_QUERY")
            if not ok:
                self._warn_or_fail(f"Failed to grant serving endpoint CAN_QUERY: {endpoint}")

    def _grant_ai_search_can_use(
        self,
        ai_search_endpoint_names: list[str],
        sp_client_id: str,
    ) -> None:
        if not ai_search_endpoint_names:
            print("INFO: No AI Search endpoints configured for target.")
            return

        for endpoint in ai_search_endpoint_names:
            if _is_placeholder(endpoint):
                continue

            endpoint_id = self._resolve_vector_endpoint_id(endpoint)
            if not endpoint_id:
                self._warn_or_fail(f"AI Search endpoint not found or inaccessible: {endpoint}")
                continue

            endpoint_ok = self._update_permissions(
                "vector-search-endpoints", endpoint_id, "CAN_USE", sp_client_id
            )
            print(
                f"AI SEARCH ENDPOINT PERMISSION: {'OK' if endpoint_ok else 'FAILED'} -> "
                f"{endpoint} CAN_USE"
            )
            if not endpoint_ok:
                self._warn_or_fail(f"Failed to grant AI Search endpoint CAN_USE: {endpoint}")

    def _grant_lakebase_postgres_role(
        self,
        lakebase_configs: list[dict[str, str]],
        sp_client_id: str,
    ) -> None:
        if not lakebase_configs:
            print("INFO: No Lakebase projects configured for target.")
            return

        for cfg in lakebase_configs:
            project_id = cfg["project_id"]
            branch_id = cfg["branch_id"]
            branch_path = f"projects/{project_id}/branches/{branch_id}"

            # Check if the SP already has a role on this branch.
            existing_roles = self.cli.run(
                ["postgres", "list-roles", branch_path, "--output", "json"],
                expect_json=True,
                check=False,
            )
            already_granted = False
            if isinstance(existing_roles, list):
                for role in existing_roles:
                    if isinstance(role, dict):
                        pg_role = (role.get("status") or role.get("spec") or {}).get(
                            "postgres_role", ""
                        )
                        if pg_role == sp_client_id:
                            already_granted = True
                            break

            if already_granted:
                print(f"LAKEBASE ROLE: ALREADY EXISTS -> {branch_path} for {sp_client_id}")
                continue

            role_id = f"sp-{self.app_name}"[:63]
            create_args = [
                "postgres",
                "create-role",
                branch_path,
                "--role-id",
                role_id,
                "--json",
                json.dumps(
                    {
                        "spec": {
                            "identity_type": "SERVICE_PRINCIPAL",
                            "postgres_role": sp_client_id,
                            "auth_method": "LAKEBASE_OAUTH_V1",
                            "membership_roles": ["DATABRICKS_SUPERUSER"],
                        }
                    }
                ),
            ]
            if self.dry_run:
                print(f"DRY RUN: databricks {' '.join(create_args)}")
                continue

            result = self.cli.run(create_args, check=False)
            ok = result.returncode == 0
            print(f"LAKEBASE ROLE: {'OK' if ok else 'FAILED'} -> {branch_path} role={role_id}")
            if not ok:
                self._warn_or_fail(
                    f"Failed to create Lakebase Postgres role on {branch_path}: "
                    f"{(result.stderr or '').strip()}"
                )

    def run(self) -> int:
        """Execute permission discovery, validation, and grant application.

        Returns:
            Exit code `0` on success. Returns `1` when failures are detected and
            `fail_open` is disabled.

        Side Effects:
            Calls Databricks APIs/CLI to update permissions and grants.

        Notes:
            The workflow is designed to be idempotent when rerun against the
            same target configuration.
        """
        target_vars = self._read_target_vars()
        sp_client_id = self._resolve_app_sp_client_id()

        print("Permission management plan")
        print("-" * 60)
        print(f"Target: {self.target}")
        print(f"App: {self.app_name}")
        print(f"Service principal client id: {sp_client_id}")

        subagent_genie, subagent_serving, ai_search_indexes, lakebase_configs = (
            self._read_subagent_resource_hints()
        )

        configured_genie = [
            target_vars.get("genie_space_id"),
            target_vars.get("store_manager_genie_space_id"),
            target_vars.get("executive_genie_space_id"),
            target_vars.get("supply_chain_genie_space_id"),
            *subagent_genie,
        ]
        genie_space_ids = sorted(
            {
                str(v).strip()
                for v in configured_genie
                if isinstance(v, str) and v.strip() and not _is_placeholder(v)
            }
        )

        configured_serving = [
            target_vars.get("serving_endpoint_name"),
            target_vars.get("knowledge_assistant_endpoint_name"),
            *subagent_serving,
        ]
        serving_endpoints = sorted(
            {
                str(v).strip()
                for v in configured_serving
                if isinstance(v, str) and v.strip() and not _is_placeholder(v)
            }
        )

        ai_search_endpoints = sorted(
            {
                str(v).strip()
                for v in [
                    target_vars.get("vector_search_endpoint_name"),
                    target_vars.get("product_index_ep"),
                    target_vars.get("flink_support_ed"),
                ]
                if isinstance(v, str) and v.strip() and not _is_placeholder(v)
            }
        )

        uc_catalog = target_vars.get("uc_audit_catalog")
        uc_schema = target_vars.get("uc_audit_schema")
        warehouse_id = target_vars.get("uc_audit_warehouse_id")
        message_bus_backend = str(target_vars.get("message_bus_backend") or "").strip().lower()

        print(f"Genie Agents: {genie_space_ids or 'none'}")
        print(f"Serving endpoints: {serving_endpoints or 'none'}")
        print(f"AI Search endpoints: {ai_search_endpoints or 'none'}")
        if ai_search_indexes:
            print(f"AI Search UC objects: {ai_search_indexes}")
        else:
            print("AI Search UC objects: none")
        if lakebase_configs:
            print(
                f"Lakebase projects: {[c['project_id'] + '/' + c['branch_id'] for c in lakebase_configs]}"
            )
        else:
            print("Lakebase projects: none")
        print(f"UC catalog/schema: {uc_catalog}.{uc_schema}")
        print(f"SQL warehouse: {warehouse_id}")
        if self.dry_run:
            print("Mode: dry-run")

        validated_ai_search = self._check_ai_search_uc_securables(ai_search_indexes)

        self._grant_genie_can_run(genie_space_ids, sp_client_id)
        self._grant_serving_can_query(serving_endpoints, sp_client_id)
        self._grant_ai_search_can_use(ai_search_endpoints, sp_client_id)
        self._grant_ai_search_uc_permissions(validated_ai_search, sp_client_id)
        self._grant_lakebase_postgres_role(lakebase_configs, sp_client_id)
        if message_bus_backend == "uc_table":
            self._grant_uc_permissions(
                str(uc_catalog) if isinstance(uc_catalog, str) else None,
                str(uc_schema) if isinstance(uc_schema, str) else None,
                str(warehouse_id) if isinstance(warehouse_id, str) else None,
                sp_client_id,
            )
        else:
            print("INFO: Skipping UC grants; message_bus_backend is not uc_table.")

        if self.failures:
            print("\nPermission management completed with issues:")
            for item in self.failures:
                print(f"- {item}")
            return 0 if self.fail_open else 1

        print("\nPermission management completed successfully.")
        return 0


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for runtime permission grants."""
    parser = argparse.ArgumentParser(
        description="Grant runtime permissions to app service principal."
    )
    parser.add_argument("--app-name", required=True, help="Databricks app name")
    parser.add_argument(
        "--target", required=True, choices=list(SUPPORTED_TARGETS), help="Bundle target"
    )
    parser.add_argument("--profile", default="DEFAULT", help="Databricks CLI profile")
    parser.add_argument("--dry-run", action="store_true", help="Preview grants without applying")
    parser.add_argument(
        "--fail-open",
        action="store_true",
        help="Do not fail the script when some permission grants fail",
    )
    return parser.parse_args()


def main() -> None:
    """Run permission manager and exit with its status code."""
    args = parse_args()
    cli = DatabricksCli(profile=args.profile)
    manager = PermissionManager(
        cli=cli,
        target=args.target,
        app_name=args.app_name,
        dry_run=args.dry_run,
        fail_open=args.fail_open,
    )
    exit_code = manager.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
