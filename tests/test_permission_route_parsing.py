from scripts.grant_app_runtime_permissions import PermissionManager


def test_permission_parser_accepts_canonical_vector_search_route():
    manager = object.__new__(PermissionManager)

    parsed = manager._parse_ai_search_mcp_url(
        "/api/2.0/mcp/vector-search/catalog/schema/product_index"
    )

    assert parsed == ("catalog", "schema", "product_index")


def test_permission_parser_retains_legacy_ai_search_route():
    manager = object.__new__(PermissionManager)

    parsed = manager._parse_ai_search_mcp_url(
        "/api/2.0/mcp/ai-search/catalog/schema/product_index"
    )

    assert parsed == ("catalog", "schema", "product_index")