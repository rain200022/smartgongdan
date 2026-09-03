# 开发约定

## 本地准备

```powershell
Copy-Item .env.example .env
uv sync
Set-Location frontend
npm install
Set-Location ..
docker compose up -d db
uv run alembic upgrade head
```

## 修改顺序

1. 先用测试固定现有行为或新增验收条件。
2. 在正确的模块边界内实现最小变更。
3. 新增数据库字段时创建新的 Alembic 迁移，不修改已经应用的迁移。
4. 运行 `quality: all` VS Code 任务或 `AGENTS.md` 中的全部命令。
5. 更新 README、项目契约和接口示例。

## 模块职责

| 目录 | 职责 |
|---|---|
| `app/api` | HTTP 路由、依赖注入、响应序列化 |
| `app/services` | 工单、分析、评估等业务用例和事务边界 |
| `app/models` | SQLAlchemy 持久化模型 |
| `app/schemas` | Pydantic 输入输出契约 |
| `app/core` | 配置、分类规则、领域异常等稳定基础能力 |
| `app/api/dependencies.py` | 当前用户与角色权限依赖 |
| `app/services/auth_service.py` | 密码、会话和账号业务用例 |
| `alembic` | 可回滚数据库迁移 |
| `tests` | 行为、边界、外部适配器和回归测试 |
| `frontend/src/api` | 前端 HTTP 契约、类型和统一错误处理 |
| `frontend/src/layouts` | 用户端和管理员端应用框架 |
| `frontend/src/views` | 面向业务流程的 Vue 页面 |
| `frontend/src/styles` | 设计令牌和全局基础样式 |

禁止在路由中拼写模型 Prompt、直接编写 SQL 或实现分类业务规则。
前端页面禁止直接调用 `fetch`、混用组件库或绕过设计令牌增加一次性颜色。

## 创建本地账号

数据库迁移完成后运行以下命令，密码会在终端中安全提示输入：

```powershell
uv run python -m scripts.create_user my-admin --display-name "本地管理员" --role ADMIN
```

可用角色为 `USER`、`ENGINEER` 和 `ADMIN`。不要在命令行参数、代码或提交记录中保存真实密码。
