"""属性ベースアクセス制御（ABAC）・有効化・実行フローのスモークテスト。

seed: alice=営業部 / bob=マーケティング部 / carol=サポート部 / dave=分析部
"""

from fastapi.testclient import TestClient

ADMIN = {"X-User-Id": "admin"}
ALICE = {"X-User-Id": "alice"}  # 営業部


def _agent_id(client: TestClient, name: str) -> str:
    agents = client.get("/api/v1/agents", headers=ADMIN).json()
    return next(a["id"] for a in agents if a["name"] == name)


def _mcp_id(client: TestClient, name: str) -> str:
    servers = client.get("/api/v1/mcp-servers", headers=ADMIN).json()
    return next(m["id"] for m in servers if m["name"] == name)


def test_auth_required(client: TestClient):
    assert client.get("/api/v1/me").status_code == 401
    assert client.get("/api/v1/me", headers={"X-User-Id": "ghost"}).status_code == 401


def test_attribute_based_allowed(client: TestClient):
    # admin はすべて allowed
    admin_agents = client.get("/api/v1/agents", headers=ADMIN).json()
    assert len(admin_agents) == 4
    assert all(a["allowed"] for a in admin_agents)

    # alice=営業部 は属性に応じて Sales Agent のみ allowed
    alice_agents = client.get("/api/v1/agents", headers=ALICE).json()
    assert len(alice_agents) == 4  # 全件表示される
    allowed = sorted(a["name"] for a in alice_agents if a["allowed"])
    assert allowed == ["Sales Agent"]

    # MCP は営業部に許可されたもの + 全社公開(KB)が allowed
    alice_mcp = client.get("/api/v1/mcp-servers", headers=ALICE).json()
    allowed_mcp = sorted(m["name"] for m in alice_mcp if m["allowed"])
    assert allowed_mcp == ["CRM MCP", "Calendar MCP", "Email MCP", "Knowledge Base MCP"]


def test_non_admin_cannot_manage(client: TestClient):
    assert client.get("/api/v1/users", headers=ALICE).status_code == 403
    sales = _agent_id(client, "Sales Agent")
    assert (
        client.put(
            f"/api/v1/agents/{sales}/access",
            headers=ALICE,
            json={"access": {"department": ["営業部"]}},
        ).status_code
        == 403
    )


def test_enable_only_allowed(client: TestClient):
    sales = _agent_id(client, "Sales Agent")  # alice 営業部 → 可
    support = _agent_id(client, "Support Agent")  # サポート部のみ → alice 不可

    ok = client.put(
        "/api/v1/me/enablements",
        headers=ALICE,
        json={"enabled_agent_ids": [sales], "enabled_mcp_server_ids": []},
    )
    assert ok.status_code == 200

    forbidden = client.put(
        "/api/v1/me/enablements",
        headers=ALICE,
        json={"enabled_agent_ids": [support], "enabled_mcp_server_ids": []},
    )
    assert forbidden.status_code == 403


def test_admin_changes_user_department_grants_access(client: TestClient):
    marketing = _agent_id(client, "Marketing Agent")
    # 営業部の alice は Marketing Agent 不可
    forbidden = client.put(
        "/api/v1/me/enablements",
        headers=ALICE,
        json={"enabled_agent_ids": [marketing], "enabled_mcp_server_ids": []},
    )
    assert forbidden.status_code == 403

    # admin が alice を マーケティング部 に変更 → 利用可になる
    client.put(
        "/api/v1/users/alice/attributes",
        headers=ADMIN,
        json={"attributes": {"department": "マーケティング部"}},
    )
    ok = client.put(
        "/api/v1/me/enablements",
        headers=ALICE,
        json={"enabled_agent_ids": [marketing], "enabled_mcp_server_ids": []},
    )
    assert ok.status_code == 200


def test_changing_resource_access_prunes_enablement(client: TestClient):
    sales = _agent_id(client, "Sales Agent")
    client.put(
        "/api/v1/me/enablements",
        headers=ALICE,
        json={"enabled_agent_ids": [sales], "enabled_mcp_server_ids": []},
    )
    assert client.get("/api/v1/me/enablements", headers=ALICE).json()["enabled_agent_ids"] == [sales]

    # admin が Sales Agent を 分析部のみ に変更 → 営業部の alice からは外れる
    client.put(
        f"/api/v1/agents/{sales}/access",
        headers=ADMIN,
        json={"access": {"department": ["分析部"]}},
    )
    enab = client.get("/api/v1/me/enablements", headers=ALICE).json()
    assert enab["enabled_agent_ids"] == []


def test_execute_requires_enabled_agent(client: TestClient):
    sales = _agent_id(client, "Sales Agent")
    # 有効化していない -> 403
    res = client.post(
        "/api/v1/execute",
        headers=ALICE,
        json={"agent_ids": [sales], "mcp_server_ids": [], "input": "hi"},
    )
    assert res.status_code == 403

    client.put(
        "/api/v1/me/enablements",
        headers=ALICE,
        json={"enabled_agent_ids": [sales], "enabled_mcp_server_ids": []},
    )
    res = client.post(
        "/api/v1/execute",
        headers=ALICE,
        json={"agent_ids": [sales], "mcp_server_ids": [], "input": "hi"},
    )
    assert res.status_code == 200
    assert res.json()["status"] in {"completed", "error"}


def test_custom_agent_create_requires_enabled(client: TestClient):
    sales = _agent_id(client, "Sales Agent")
    crm = _mcp_id(client, "CRM MCP")

    rejected = client.post(
        "/api/v1/me/custom-agents",
        headers=ALICE,
        json={"name": "sales-bot", "agent_ids": [sales], "mcp_server_ids": [crm]},
    )
    assert rejected.status_code == 400

    client.put(
        "/api/v1/me/enablements",
        headers=ALICE,
        json={"enabled_agent_ids": [sales], "enabled_mcp_server_ids": [crm]},
    )
    created = client.post(
        "/api/v1/me/custom-agents",
        headers=ALICE,
        json={"name": "sales-bot", "agent_ids": [sales], "mcp_server_ids": [crm]},
    )
    assert created.status_code == 201
    custom_id = created.json()["id"]

    listed = client.get("/api/v1/me/custom-agents", headers=ALICE).json()
    assert [c["id"] for c in listed] == [custom_id]

    run = client.post(
        f"/api/v1/me/custom-agents/{custom_id}/run",
        headers=ALICE,
        json={"agent_ids": [], "mcp_server_ids": [], "input": "状況を教えて"},
    )
    assert run.status_code == 200

    # 他人のカスタム Agent は見えない / 実行できない
    assert (
        client.post(
            f"/api/v1/me/custom-agents/{custom_id}/run",
            headers={"X-User-Id": "bob"},
            json={"agent_ids": [], "mcp_server_ids": [], "input": "x"},
        ).status_code
        == 404
    )
