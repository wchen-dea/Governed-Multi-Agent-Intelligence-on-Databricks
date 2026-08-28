import json

import pytest

from aiserver.contracts.subagents import load_subagents, parse_subagents


def test_load_subagents_valid_defaults(tmp_path):
    config = [
        {
            "name": "sales_insights_agent",
            "type": "genie",
            "data_classification": "confidential",
            "owner": "sales-analytics",
            "freshness_sla": "15m",
            "allowed_personas": ["analyst"],
            "requires_evidence": True,
            "space_id": "space-1",
            "description": "genie",
        },
        {
            "name": "knowledge_assistant",
            "type": "serving_endpoint",
            "data_classification": "internal",
            "owner": "platform-docs",
            "freshness_sla": "24h",
            "allowed_personas": ["analyst"],
            "requires_evidence": False,
            "endpoint": "knowledge_assistant",
            "description": "serving",
        },
    ]
    config_path = tmp_path / "subagents.json"
    config_path.write_text(json.dumps(config))

    subagents = load_subagents(config_path)

    assert len(subagents) == 2
    assert subagents[0].auth_mode == "obo"
    assert subagents[1].auth_mode == "app"
    assert subagents[0].data_classification == "confidential"
    assert subagents[1].allowed_personas == ("analyst",)


def test_load_subagents_missing_file_raises_value_error(tmp_path):
    missing_path = tmp_path / "does_not_exist.json"

    with pytest.raises(ValueError, match="file not found"):
        load_subagents(missing_path)


def test_load_subagents_invalid_root_type_raises_value_error(tmp_path):
    config_path = tmp_path / "subagents.json"
    config_path.write_text(json.dumps({"name": "not-a-list"}))

    with pytest.raises(ValueError, match="root must be a list"):
        load_subagents(config_path)


@pytest.mark.parametrize(
    ("raw", "msg"),
    [
        (
            [
                {
                    "name": "bad_kind",
                    "type": "invalid",
                    "data_classification": "internal",
                    "owner": "owner",
                    "freshness_sla": "1h",
                    "allowed_personas": ["analyst"],
                    "requires_evidence": False,
                    "description": "x",
                    "endpoint": "ep",
                }
            ],
            "unsupported type",
        ),
        (
            [
                {
                    "name": "bad_auth",
                    "type": "serving_endpoint",
                    "data_classification": "internal",
                    "owner": "owner",
                    "freshness_sla": "1h",
                    "allowed_personas": ["analyst"],
                    "requires_evidence": False,
                    "auth_mode": "invalid",
                    "description": "x",
                    "endpoint": "ep",
                }
            ],
            "unsupported auth_mode",
        ),
        (
            [
                {
                    "name": "missing_space",
                    "type": "genie",
                    "data_classification": "internal",
                    "owner": "owner",
                    "freshness_sla": "1h",
                    "allowed_personas": ["analyst"],
                    "requires_evidence": False,
                    "description": "x",
                }
            ],
            "must define space_id",
        ),
        (
            [
                {
                    "name": "missing_endpoint",
                    "type": "serving_endpoint",
                    "data_classification": "internal",
                    "owner": "owner",
                    "freshness_sla": "1h",
                    "allowed_personas": ["analyst"],
                    "requires_evidence": False,
                    "description": "x",
                }
            ],
            "must define endpoint",
        ),
        (
            [
                {
                    "name": "bad_classification",
                    "type": "serving_endpoint",
                    "owner": "owner",
                    "freshness_sla": "1h",
                    "allowed_personas": ["analyst"],
                    "requires_evidence": False,
                    "description": "x",
                    "endpoint": "ep",
                    "data_classification": "secret",
                }
            ],
            "unsupported data_classification",
        ),
        (
            [
                {
                    "name": "bad_personas",
                    "type": "serving_endpoint",
                    "data_classification": "internal",
                    "owner": "owner",
                    "freshness_sla": "1h",
                    "requires_evidence": False,
                    "description": "x",
                    "endpoint": "ep",
                    "allowed_personas": "analyst",
                }
            ],
            "allowed_personas must be a list of strings",
        ),
        (
            [
                {
                    "name": "missing_metadata",
                    "type": "serving_endpoint",
                    "description": "x",
                    "endpoint": "ep",
                }
            ],
            "missing required metadata fields",
        ),
        (
            [
                {
                    "name": "empty_personas",
                    "type": "serving_endpoint",
                    "description": "x",
                    "endpoint": "ep",
                    "data_classification": "internal",
                    "owner": "owner",
                    "freshness_sla": "1h",
                    "allowed_personas": [],
                    "requires_evidence": False,
                }
            ],
            "must define at least one allowed_personas entry",
        ),
    ],
)
def test_parse_subagents_invalid_entries_raise_value_error(raw, msg):
    with pytest.raises(ValueError, match=msg):
        parse_subagents(raw)


def test_parse_subagents_accepts_governance_metadata():
    subagents = parse_subagents(
        [
            {
                "name": "governed_agent",
                "type": "serving_endpoint",
                "description": "x",
                "endpoint": "ep",
                "data_classification": "restricted",
                "owner": "data-governance",
                "freshness_sla": "1h",
                "allowed_personas": ["analyst", "manager"],
                "requires_evidence": True,
            }
        ]
    )

    assert len(subagents) == 1
    assert subagents[0].data_classification == "restricted"
    assert subagents[0].owner == "data-governance"
    assert subagents[0].freshness_sla == "1h"
    assert subagents[0].allowed_personas == ("analyst", "manager")
    assert subagents[0].requires_evidence is True


def test_parse_subagents_accepts_human_approval_agent():
    subagents = parse_subagents(
        [
            {
                "name": "store_intervention_agent",
                "type": "app",
                "description": "review store interventions before action",
                "endpoint": "store_intervention_agent",
                "data_classification": "confidential",
                "owner": "sales-operations",
                "freshness_sla": "15m",
                "allowed_personas": ["manager"],
                "requires_evidence": True,
                "requires_human_approval": True,
            }
        ]
    )

    assert len(subagents) == 1
    assert subagents[0].name == "store_intervention_agent"
    assert subagents[0].allowed_personas == ("manager",)
    assert subagents[0].requires_human_approval is True


def test_parse_subagents_accepts_mcp_subagent():
    subagents = parse_subagents(
        [
            {
                "name": "product_search",
                "type": "mcp",
                "description": "search products",
                "mcp_url": "/api/2.0/mcp/ai-search/catalog/schema/index",
                "data_classification": "internal",
                "owner": "platform-docs",
                "freshness_sla": "24h",
                "allowed_personas": ["manager"],
                "requires_evidence": False,
            }
        ]
    )

    assert len(subagents) == 1
    assert subagents[0].kind == "mcp"
    assert subagents[0].mcp_url == "/api/2.0/mcp/ai-search/catalog/schema/index"


def test_parse_subagents_accepts_system_prompt():
    subagents = parse_subagents(
        [
            {
                "name": "sales_insights_agent",
                "type": "genie",
                "description": "sales genie",
                "system_prompt": "Always answer with clear KPI labels.",
                "space_id": "space-1",
                "data_classification": "confidential",
                "owner": "sales-analytics",
                "freshness_sla": "15m",
                "allowed_personas": ["manager"],
                "requires_evidence": True,
            }
        ]
    )

    assert len(subagents) == 1
    assert subagents[0].system_prompt == "Always answer with clear KPI labels."


def test_load_subagents_skips_placeholder_identifiers(tmp_path):
    config = [
        {
            "name": "store_manager_genie",
            "type": "genie",
            "data_classification": "confidential",
            "owner": "store-operations",
            "freshness_sla": "15m",
            "allowed_personas": ["manager"],
            "requires_evidence": True,
            "space_id": "<STORE-MANAGER-GENIE-SPACE-ID>",
            "description": "placeholder genie",
        },
        {
            "name": "sales_insights_agent",
            "type": "genie",
            "data_classification": "confidential",
            "owner": "sales-analytics",
            "freshness_sla": "15m",
            "allowed_personas": ["manager"],
            "requires_evidence": True,
            "space_id": "01f159f5d91419549020e3609add391c",
            "description": "configured genie",
        },
    ]
    config_path = tmp_path / "subagents.json"
    config_path.write_text(json.dumps(config))

    subagents = load_subagents(config_path)

    assert len(subagents) == 1
    assert subagents[0].name == "sales_insights_agent"


def test_load_subagents_resolves_path_from_target_env(tmp_path, monkeypatch):
    config = [
        {
            "name": "sales_insights_agent",
            "type": "genie",
            "data_classification": "confidential",
            "owner": "sales-analytics",
            "freshness_sla": "15m",
            "allowed_personas": ["analyst"],
            "requires_evidence": True,
            "space_id": "space-1",
            "description": "genie",
        }
    ]
    config_path = tmp_path / "subagents.qa.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    monkeypatch.setenv("DATABRICKS_BUNDLE_TARGET", "qa")
    monkeypatch.delenv("SUBAGENTS_CONFIG_PATH", raising=False)

    import aiserver.contracts.subagents as subagent_config

    monkeypatch.setattr(subagent_config, "__file__", str(tmp_path / "subagent_config.py"))

    subagents = subagent_config.load_subagents()

    assert len(subagents) == 1
    assert subagents[0].name == "sales_insights_agent"


def test_load_subagents_raises_helpful_error_when_unresolvable(tmp_path, monkeypatch):
    monkeypatch.delenv("SUBAGENTS_CONFIG_PATH", raising=False)
    monkeypatch.delenv("DATABRICKS_BUNDLE_TARGET", raising=False)
    monkeypatch.delenv("BUNDLE_TARGET", raising=False)
    monkeypatch.delenv("TARGET", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)

    import aiserver.contracts.subagents as subagent_config

    monkeypatch.setattr(subagent_config, "__file__", str(tmp_path / "subagent_config.py"))

    with pytest.raises(ValueError, match="Could not resolve subagent configuration file"):
        subagent_config.load_subagents()
