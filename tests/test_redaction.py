from app.services.redaction_service import redact_mapping, redact_text


def test_redact_text_removes_common_identifiers_and_secrets() -> None:
    source = (
        r"联系人 alice@example.com，手机 13812345678，IP 10.20.30.40，"
        r"路径 C:\Users\alice\vpn.log，MAC AA:BB:CC:DD:EE:FF，"
        r"身份证 110101199001011234，token=abc.def.ghi，密码：MySecret123"
    )

    result = redact_text(source)

    for sensitive in (
        "alice@example.com",
        "13812345678",
        "10.20.30.40",
        "alice\\vpn.log",
        "AA:BB:CC:DD:EE:FF",
        "110101199001011234",
        "abc.def.ghi",
        "MySecret123",
    ):
        assert sensitive not in result
    assert "[EMAIL]" in result
    assert "[PHONE]" in result
    assert "[IP_ADDRESS]" in result
    assert r"C:\Users\[USER]\vpn.log" in result
    assert "[MAC_ADDRESS]" in result
    assert "[ID_NUMBER]" in result
    assert result.count("[SENSITIVE]") == 2


def test_redact_text_preserves_diagnostic_content() -> None:
    source = "VPN 错误代码 691，设备证书过期，HTTPS 端口 443，影响单用户。"

    assert redact_text(source) == source


def test_redact_mapping_is_recursive_and_does_not_mutate_input() -> None:
    payload: dict[str, object] = {
        "title": "邮箱 alice@example.com 无法登录",
        "attempted_actions": ["联系 13812345678", "重启客户端"],
        "evidence": {"content": "server=10.0.0.8"},
        "ticket_id": 7,
    }

    result = redact_mapping(payload)

    assert payload["title"] == "邮箱 alice@example.com 无法登录"
    assert result == {
        "title": "邮箱 [EMAIL] 无法登录",
        "attempted_actions": ["联系 [PHONE]", "重启客户端"],
        "evidence": {"content": "server=[IP_ADDRESS]"},
        "ticket_id": 7,
    }
