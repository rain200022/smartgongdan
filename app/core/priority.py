from enum import StrEnum


class ImpactLevel(StrEnum):
    CORE_BUSINESS = "核心业务受影响"
    BUSINESS_LIMITED = "业务功能受限"
    INDIVIDUAL_WORK = "个人工作受影响"
    MINOR = "轻微影响"


class UrgencyLevel(StrEnum):
    HIGH = "高"
    MEDIUM = "中"
    LOW = "低"


class AffectedScope(StrEnum):
    COMPANY = "全公司"
    MULTIPLE_DEPARTMENTS = "多部门"
    MULTIPLE_USERS = "多用户"
    SINGLE_USER = "单用户"
