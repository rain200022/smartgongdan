from enum import StrEnum


class TicketCategory(StrEnum):
    NETWORK = "网络"
    SOFTWARE = "软件"
    ACCOUNT = "账号"
    HARDWARE = "硬件"
    OTHER = "其他"


CLASSIFICATION_TREE: dict[TicketCategory, tuple[str, ...]] = {
    TicketCategory.NETWORK: ("VPN", "WiFi", "DNS", "网络不可用"),
    TicketCategory.SOFTWARE: ("安装失败", "启动失败", "崩溃", "配置问题"),
    TicketCategory.ACCOUNT: ("无法登录", "密码", "权限"),
    TicketCategory.HARDWARE: ("电脑", "显示器", "打印机", "外设"),
    TicketCategory.OTHER: ("未分类",),
}


def classification_tree_text() -> str:
    return "\n".join(
        f"{category.value}: {', '.join(subcategories)}"
        for category, subcategories in CLASSIFICATION_TREE.items()
    )


def validate_classification(category: str, subcategory: str) -> TicketCategory:
    try:
        normalized_category = TicketCategory(category)
    except ValueError as exc:
        raise ValueError(f"unknown category '{category}'") from exc
    if subcategory not in CLASSIFICATION_TREE[normalized_category]:
        raise ValueError(f"subcategory '{subcategory}' is invalid for category '{category}'")
    return normalized_category


def split_classification(value: str) -> tuple[str, str]:
    normalized = value.replace("／", "/")
    category, separator, subcategory = normalized.partition("/")
    return category.strip(), subcategory.strip() if separator else "未分类"


def join_classification(category: str, subcategory: str) -> str:
    return f"{category}/{subcategory}"
