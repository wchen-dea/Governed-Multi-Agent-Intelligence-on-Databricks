from operations.databricks_apps_client import DatabricksAppsClient


class FakeApi:
    def __init__(self):
        self.calls = []
        self.responses = [
            {
                "app_status": {"state": "STARTING"},
                "active_deployment": {"status": {"state": "SUCCEEDED"}},
            },
            {
                "app_status": {"state": "RUNNING"},
                "active_deployment": {
                    "deployment_id": "dep-1",
                    "status": {"state": "SUCCEEDED"},
                },
            },
        ]

    def do(self, method, path, body=None):
        self.calls.append((method, path, body))
        if method == "GET":
            return self.responses.pop(0)
        return {"deployment_id": "dep-1"}


class FakeWorkspace:
    def __init__(self, api):
        self.api_client = api


def test_wait_for_health_polls_until_running():
    api = FakeApi()
    client = DatabricksAppsClient(FakeWorkspace(api), sleep=lambda _: None, monotonic=iter([0, 1, 2]).__next__)

    result = client.wait_for_health("my app", timeout_seconds=10)

    assert result.healthy
    assert api.calls[0][1] == "/api/2.0/apps/my%20app"
    assert len([call for call in api.calls if call[0] == "GET"]) == 2


def test_deploy_snapshot_and_start_use_apps_api():
    api = FakeApi()
    client = DatabricksAppsClient(FakeWorkspace(api))

    client.deploy_snapshot("app", "/Workspace/source")
    client.start("app")

    assert api.calls == [
        (
            "POST",
            "/api/2.0/apps/app/deployments",
            {"source_code_path": "/Workspace/source", "mode": "SNAPSHOT"},
        ),
        ("POST", "/api/2.0/apps/app/start", {}),
    ]