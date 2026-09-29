import json

from operations.grant_app_runtime_permissions import PermissionManager


def test_permission_parser_accepts_canonical_vector_search_route():
    manager = object.__new__(PermissionManager)

    parsed = manager._parse_ai_search_mcp_url(
        "/api/2.0/mcp/vector-search/catalog/schema/product_index"
    )

    assert parsed == ("catalog", "schema", "product_index")


def test_permission_parser_retains_legacy_ai_search_route():
    manager = object.__new__(PermissionManager)

    parsed = manager._parse_ai_search_mcp_url("/api/2.0/mcp/ai-search/catalog/schema/product_index")

    assert parsed == ("catalog", "schema", "product_index")


def test_permission_manager_reads_lakebase_hints_from_contracts(tmp_path, monkeypatch):
    config_dir = tmp_path / "src" / "aiserver" / "contracts"
    config_dir.mkdir(parents=True)
    (config_dir / "subagents.dev.json").write_text(
        json.dumps(
            [
                {
                    "name": "lakebase",
                    "type": "lakebase",
                    "project_id": "project",
                    "branch_id": "branch",
                    "endpoint_id": "primary",
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    manager = object.__new__(PermissionManager)
    manager.target = "dev"

    _, _, _, lakebase_configs = manager._read_subagent_resource_hints()

    assert lakebase_configs == [
        {
            "project_id": "project",
            "branch_id": "branch",
            "endpoint_id": "primary",
        }
    ]
