import json
import re
from functools import lru_cache
from typing import Protocol

import httpx
from pydantic import ValidationError

from app.core.classification import TicketCategory, classification_tree_text
from app.core.config import Settings, get_settings
from app.core.exceptions import AIServiceError
from app.core.priority import AffectedScope, ImpactLevel, UrgencyLevel
from app.schemas.ai_analysis import TicketAIAnalysis
from app.schemas.solution import TicketAISolutionDraft, TicketSolutionContext
from app.services.redaction_service import redact_mapping

SYSTEM_PROMPT = f"""你是企业 IT 服务台工单分析助手。
你只能生成摘要、判断分类，并提取设备、故障现象、明确错误信息、用户已尝试的操作、
影响程度、紧急度和影响范围。
你不能解决问题，不能提出解决步骤，也不得编造用户没有提供的信息。
你不能直接决定 P1/P2/P3/P4，优先级将由系统规则根据提取事实计算。
category 和 subcategory 只能从以下分类树中选择：
{classification_tree_text()}
无法确定时必须使用 其他 / 未分类。
impact 只能是：核心业务受影响、业务功能受限、个人工作受影响、轻微影响。
urgency 只能是：高、中、低。
affected_scope 只能是：全公司、多部门、多用户、单用户。
文本未明确多人或更大范围时，affected_scope 必须使用单用户。
输入中的方括号占位符表示已脱敏内容，不得尝试还原或猜测原值。
只返回符合给定 JSON Schema 的数据。"""

SOLUTION_SYSTEM_PROMPT = """你是企业 IT 服务台处理建议助手。
只能根据输入中的 retrieved evidence 生成诊断和排障步骤，不得使用外部事实或编造引用。
referenced_cases 只能填写 evidence 中存在的 reference。
不要重复 attempted_actions 中用户已经尝试过的操作。
证据不足、步骤可能产生风险或必须由专业人员操作时，将 need_human 设为 true。
建议只供工程师审核，不得声称已执行操作或已解决工单。
输入中的方括号占位符表示已脱敏内容，不得尝试还原或猜测原值。
只返回符合给定 JSON Schema 的数据。"""


class TicketContent(Protocol):
    title: str
    description: str


class AIService(Protocol):
    model_name: str

    def analyze_ticket(self, ticket: TicketContent) -> TicketAIAnalysis: ...

    def generate_solution(self, context: TicketSolutionContext) -> TicketAISolutionDraft: ...


class LocalAIService:
    """Deterministic M1 development adapter; replace through AI_PROVIDER in production."""

    def __init__(self, model_name: str = "local-rules-v1") -> None:
        self.model_name = model_name

    _classification_rules = (
        (TicketCategory.NETWORK, "VPN", ("vpn", "虚拟专用网")),
        (TicketCategory.NETWORK, "WiFi", ("wifi", "wi-fi", "无线网", "无线网络")),
        (TicketCategory.NETWORK, "DNS", ("dns", "域名解析")),
        (TicketCategory.NETWORK, "网络不可用", ("断网", "无法上网", "网络不可用")),
        (TicketCategory.HARDWARE, "打印机", ("打印机", "打印")),
        (TicketCategory.HARDWARE, "电脑", ("电脑开机", "无法开机", "笔记本无法开机")),
        (TicketCategory.HARDWARE, "显示器", ("显示器", "屏幕", "黑屏")),
        (TicketCategory.ACCOUNT, "密码", ("忘记密码", "密码过期", "重置密码", "修改密码")),
        (TicketCategory.ACCOUNT, "权限", ("权限", "无权", "访问被拒绝")),
        (
            TicketCategory.ACCOUNT,
            "无法登录",
            ("无法登录", "登录失败", "登陆失败", "账号锁定", "账号被锁定"),
        ),
        (TicketCategory.SOFTWARE, "安装失败", ("安装失败", "无法安装", "装不上")),
        (TicketCategory.SOFTWARE, "崩溃", ("崩溃", "闪退", "无响应")),
        (TicketCategory.SOFTWARE, "启动失败", ("启动失败", "无法启动", "打不开")),
        (TicketCategory.SOFTWARE, "配置问题", ("配置", "设置")),
        (TicketCategory.HARDWARE, "外设", ("鼠标", "键盘", "摄像头", "耳机")),
        (TicketCategory.HARDWARE, "电脑", ("电脑", "笔记本", "开机")),
    )

    def analyze_ticket(self, ticket: TicketContent) -> TicketAIAnalysis:
        text = f"{ticket.title}\n{ticket.description}"
        lowered = text.lower()
        category = TicketCategory.OTHER
        subcategory = "未分类"
        for candidate_category, candidate_subcategory, keywords in self._classification_rules:
            if any(keyword in lowered for keyword in keywords):
                category = candidate_category
                subcategory = candidate_subcategory
                break

        device = self._extract_device(text)
        error_message = self._extract_error_message(ticket.description)
        actions = self._extract_attempted_actions(ticket.description)
        impact = self._extract_impact(text)
        urgency = self._extract_urgency(text, impact)
        affected_scope = self._extract_affected_scope(text)
        confidence = 0.85 if category is not TicketCategory.OTHER else 0.35
        summary = ticket.title.strip()
        if error_message and error_message not in summary:
            summary = f"{summary}：{error_message}"

        return TicketAIAnalysis(
            summary=summary[:500],
            category=category,
            subcategory=subcategory,
            device=device,
            symptom=ticket.title.strip()[:1_000],
            error_message=error_message,
            attempted_actions=actions,
            impact=impact,
            urgency=urgency,
            affected_scope=affected_scope,
            confidence=confidence,
        )

    def generate_solution(self, context: TicketSolutionContext) -> TicketAISolutionDraft:
        if not context.evidence:
            return TicketAISolutionDraft(
                diagnosis="当前没有可核验的知识或历史案例，暂时无法形成可靠诊断。",
                possible_causes=[],
                steps=[],
                referenced_cases=[],
                need_human=True,
            )

        evidence = context.evidence[:3]
        references = [item.reference for item in evidence]
        possible_causes: list[str] = []
        step_candidates: list[str] = []
        for item in evidence:
            cause_match = re.search(r"([^，。；;]{2,60})(?:导致|引起|造成)", item.excerpt)
            if cause_match:
                possible_causes.append(cause_match.group(1).strip())
            source = item.resolution or item.excerpt
            step_candidates.extend(
                segment.strip()
                for segment in re.split(r"[，,。；;\n]|(?:然后)|(?:之后)|(?:并)", source)
                if segment.strip()
            )
        steps = list(dict.fromkeys(step_candidates))[:8]
        return TicketAISolutionDraft(
            diagnosis=(
                f"当前症状与 {evidence[0].reference}（{evidence[0].title}）最接近，"
                "建议先按引用证据核查，最终根因需由工程师确认。"
            ),
            possible_causes=list(dict.fromkeys(possible_causes)),
            steps=steps,
            referenced_cases=references,
            need_human=False,
        )

    @staticmethod
    def _extract_device(text: str) -> str | None:
        devices = ("公司笔记本", "笔记本", "台式机", "电脑", "打印机", "显示器", "手机")
        return next((device for device in devices if device in text), None)

    @staticmethod
    def _extract_error_message(description: str) -> str | None:
        match = re.search(r"(?:提示|报错|错误(?:信息)?)[：:]?\s*([^，。；;\n]+)", description)
        return match.group(1).strip()[:1_000] if match else None

    @staticmethod
    def _extract_attempted_actions(description: str) -> list[str]:
        segments = re.split(r"[，。；;\n]", description)
        markers = ("已经", "已尝试", "尝试了", "试过", "重启", "重新启动")
        results = []
        for segment in segments:
            cleaned = segment.strip()
            if cleaned and any(marker in cleaned for marker in markers):
                cleaned = re.sub(r"^(我)?(已经|已尝试|尝试了|试过)", "", cleaned).strip()
                if cleaned and cleaned not in results:
                    results.append(cleaned[:500])
        return results[:20]

    @staticmethod
    def _extract_impact(text: str) -> ImpactLevel:
        core_markers = ("核心业务", "生产系统", "业务中断", "无法办公", "支付", "收银")
        limited_markers = (
            "无法",
            "失败",
            "不可用",
            "中断",
            "打不开",
            "拒绝访问",
            "无权访问",
        )
        individual_markers = ("变慢", "频繁", "间歇", "闪退", "无信号", "异常")
        if any(marker in text for marker in core_markers):
            return ImpactLevel.CORE_BUSINESS
        if any(marker in text for marker in limited_markers):
            return ImpactLevel.BUSINESS_LIMITED
        if any(marker in text for marker in individual_markers):
            return ImpactLevel.INDIVIDUAL_WORK
        return ImpactLevel.MINOR

    @staticmethod
    def _extract_urgency(text: str, impact: ImpactLevel) -> UrgencyLevel:
        high_markers = ("紧急", "立即", "马上", "生产", "客户现场", "截止", "无法办公")
        medium_markers = ("无法", "失败", "不可用", "中断", "打不开", "锁定")
        if impact is ImpactLevel.CORE_BUSINESS or any(marker in text for marker in high_markers):
            return UrgencyLevel.HIGH
        if any(marker in text for marker in medium_markers):
            return UrgencyLevel.MEDIUM
        return UrgencyLevel.LOW

    @staticmethod
    def _extract_affected_scope(text: str) -> AffectedScope:
        company_markers = ("全公司", "全员", "所有员工", "所有人")
        department_markers = ("多个部门", "多部门", "跨部门")
        user_markers = ("多人", "多名用户", "多个用户", "团队", "其他同事也")
        if any(marker in text for marker in company_markers):
            return AffectedScope.COMPANY
        if any(marker in text for marker in department_markers):
            return AffectedScope.MULTIPLE_DEPARTMENTS
        if any(marker in text for marker in user_markers):
            return AffectedScope.MULTIPLE_USERS
        return AffectedScope.SINGLE_USER


class OpenAICompatibleAIService:
    def __init__(self, settings: Settings) -> None:
        if not settings.ai_api_key:
            raise AIServiceError("AI_API_KEY is required when AI_PROVIDER=openai_compatible")
        self.model_name = settings.ai_model
        self._api_key = settings.ai_api_key
        self._url = f"{settings.ai_base_url.rstrip('/')}/chat/completions"
        self._timeout = settings.ai_timeout_seconds

    def analyze_ticket(self, ticket: TicketContent) -> TicketAIAnalysis:
        outbound_ticket = redact_mapping({"title": ticket.title, "description": ticket.description})
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(outbound_ticket, ensure_ascii=False),
                },
            ],
            "temperature": 0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "ticket_ai_analysis",
                    "strict": True,
                    "schema": TicketAIAnalysis.model_json_schema(),
                },
            },
        }
        try:
            response = httpx.post(
                self._url,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=payload,
                timeout=self._timeout,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return TicketAIAnalysis.model_validate_json(content)
        except (httpx.HTTPError, KeyError, TypeError, ValueError, ValidationError) as exc:
            raise AIServiceError("AI provider returned an invalid analysis") from exc

    def generate_solution(self, context: TicketSolutionContext) -> TicketAISolutionDraft:
        outbound_context = redact_mapping(context.model_dump(mode="json"))
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": SOLUTION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(outbound_context, ensure_ascii=False),
                },
            ],
            "temperature": 0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "ticket_ai_solution",
                    "strict": True,
                    "schema": TicketAISolutionDraft.model_json_schema(),
                },
            },
        }
        try:
            response = httpx.post(
                self._url,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=payload,
                timeout=self._timeout,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return TicketAISolutionDraft.model_validate_json(content)
        except (httpx.HTTPError, KeyError, TypeError, ValueError, ValidationError) as exc:
            raise AIServiceError("AI provider returned an invalid solution") from exc


@lru_cache
def get_ai_service() -> AIService:
    settings = get_settings()
    if settings.ai_provider == "local":
        return LocalAIService(settings.ai_model)
    if settings.ai_provider == "openai_compatible":
        return OpenAICompatibleAIService(settings)
    raise AIServiceError(f"Unsupported AI_PROVIDER: {settings.ai_provider}")
