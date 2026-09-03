import json
from types import SimpleNamespace

import httpx
import pytest

from app.core.config import Settings
from app.core.exceptions import AIServiceError
from app.schemas.solution import SolutionEvidence, TicketSolutionContext
from app.services.ai_service import OpenAICompatibleAIService


def provider_settings() -> Settings:
    return Settings(
        _env_file=None,
        ai_provider="openai_compatible",
        ai_model="test-model",
        ai_base_url="https://provider.example/v1",
        ai_api_key="test-key",
    )


def test_openai_compatible_provider_requests_structured_output(monkeypatch) -> None:
    captured: dict = {}

    def fake_post(url, *, headers, json, timeout):
        captured.update(url=url, headers=headers, payload=json, timeout=timeout)
        request = httpx.Request("POST", url)
        return httpx.Response(
            200,
            request=request,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json_module.dumps(
                                {
                                    "summary": "VPN认证失败",
                                    "category": "网络",
                                    "subcategory": "VPN",
                                    "device": None,
                                    "symptom": "VPN无法连接",
                                    "error_message": "认证服务器不可用",
                                    "attempted_actions": ["重启客户端"],
                                    "impact": "业务功能受限",
                                    "urgency": "中",
                                    "affected_scope": "单用户",
                                    "confidence": 0.92,
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            },
        )

    json_module = json
    monkeypatch.setattr(httpx, "post", fake_post)
    service = OpenAICompatibleAIService(provider_settings())
    ticket = SimpleNamespace(title="VPN无法连接", description="提示认证服务器不可用")

    analysis = service.analyze_ticket(ticket)

    assert analysis.category.value == "网络"
    assert analysis.impact.value == "业务功能受限"
    assert captured["url"] == "https://provider.example/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["payload"]["response_format"]["type"] == "json_schema"
    assert captured["payload"]["response_format"]["json_schema"]["strict"] is True
    schema = captured["payload"]["response_format"]["json_schema"]["schema"]
    assert schema["additionalProperties"] is False


def test_openai_compatible_provider_rejects_invalid_classification(monkeypatch) -> None:
    def fake_post(url, **_kwargs):
        request = httpx.Request("POST", url)
        return httpx.Response(
            200,
            request=request,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"summary":"x","category":"网络",'
                            '"subcategory":"模型发明的分类","confidence":0.9}'
                        }
                    }
                ]
            },
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    service = OpenAICompatibleAIService(provider_settings())
    ticket = SimpleNamespace(title="x", description="x")

    with pytest.raises(AIServiceError):
        service.analyze_ticket(ticket)


def test_openai_compatible_provider_generates_structured_cited_solution(monkeypatch) -> None:
    captured: dict = {}

    def fake_post(url, *, headers, json, timeout):
        captured.update(url=url, headers=headers, payload=json, timeout=timeout)
        request = httpx.Request("POST", url)
        return httpx.Response(
            200,
            request=request,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json_module.dumps(
                                {
                                    "diagnosis": "可能为设备证书过期",
                                    "possible_causes": ["设备证书过期"],
                                    "steps": ["检查设备证书有效期"],
                                    "referenced_cases": ["KB001"],
                                    "need_human": False,
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            },
        )

    json_module = json
    monkeypatch.setattr(httpx, "post", fake_post)
    service = OpenAICompatibleAIService(provider_settings())
    context = TicketSolutionContext(
        ticket_id=1,
        title="VPN无法连接",
        description="认证失败，已重启客户端",
        summary="VPN认证失败",
        category="网络",
        subcategory="VPN",
        attempted_actions=["重启客户端"],
        evidence=[
            SolutionEvidence(
                reference="KB001",
                source_type="knowledge",
                title="VPN认证失败处理",
                excerpt="检查设备证书有效期。",
                resolution=None,
            )
        ],
    )

    solution = service.generate_solution(context)

    assert solution.referenced_cases == ["KB001"]
    assert solution.steps == ["检查设备证书有效期"]
    assert captured["payload"]["response_format"]["json_schema"]["strict"] is True
    user_content = json.loads(captured["payload"]["messages"][1]["content"])
    assert user_content["attempted_actions"] == ["重启客户端"]
    assert user_content["evidence"][0]["reference"] == "KB001"


def test_openai_provider_redacts_ticket_data_before_transport(monkeypatch) -> None:
    captured: dict = {}

    def fake_post(url, *, headers, json, timeout):
        captured.update(payload=json)
        request = httpx.Request("POST", url)
        return httpx.Response(
            200,
            request=request,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json_module.dumps(
                                {
                                    "summary": "VPN认证失败",
                                    "category": "网络",
                                    "subcategory": "VPN",
                                    "device": None,
                                    "symptom": "VPN无法连接",
                                    "error_message": "认证失败",
                                    "attempted_actions": [],
                                    "impact": "个人工作受影响",
                                    "urgency": "中",
                                    "affected_scope": "单用户",
                                    "confidence": 0.8,
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            },
        )

    json_module = json
    monkeypatch.setattr(httpx, "post", fake_post)
    service = OpenAICompatibleAIService(provider_settings())
    ticket = SimpleNamespace(
        title="alice@example.com 的 VPN 无法连接",
        description="手机 13812345678，IP 10.0.0.8，token=secret-token",
    )

    service.analyze_ticket(ticket)

    outbound = captured["payload"]["messages"][1]["content"]
    assert "alice@example.com" not in outbound
    assert "13812345678" not in outbound
    assert "10.0.0.8" not in outbound
    assert "secret-token" not in outbound
    assert "[EMAIL]" in outbound
    assert ticket.title == "alice@example.com 的 VPN 无法连接"


def test_openai_provider_redacts_nested_solution_context(monkeypatch) -> None:
    captured: dict = {}

    def fake_post(url, *, headers, json, timeout):
        captured.update(payload=json)
        request = httpx.Request("POST", url)
        return httpx.Response(
            200,
            request=request,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json_module.dumps(
                                {
                                    "diagnosis": "需要核查",
                                    "possible_causes": [],
                                    "steps": [],
                                    "referenced_cases": ["KB001"],
                                    "need_human": True,
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            },
        )

    json_module = json
    monkeypatch.setattr(httpx, "post", fake_post)
    service = OpenAICompatibleAIService(provider_settings())
    context = TicketSolutionContext(
        ticket_id=1,
        title="VPN无法连接",
        description="联系人 alice@example.com",
        summary="VPN认证失败",
        category="网络",
        subcategory="VPN",
        attempted_actions=["已联系 13812345678"],
        evidence=[
            SolutionEvidence(
                reference="KB001",
                source_type="knowledge",
                title="VPN认证失败处理",
                excerpt="管理地址 10.0.0.8，password=secret-value",
                resolution=None,
            )
        ],
    )

    service.generate_solution(context)

    outbound = captured["payload"]["messages"][1]["content"]
    assert "alice@example.com" not in outbound
    assert "13812345678" not in outbound
    assert "10.0.0.8" not in outbound
    assert "secret-value" not in outbound
    assert context.description == "联系人 alice@example.com"
