# Smart Gongdan（M0）

一个不依赖 AI 的最小工单后端：创建工单、查询工单、工程师处理并关闭工单。当前阶段有意不包含前端、模型调用和知识库检索。

## 环境要求

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Docker Desktop（用于 PostgreSQL）

## 在 VS Code 中启动

1. 用 VS Code 打开本目录，并复制环境配置：

   ```powershell
   Copy-Item .env.example .env
   uv sync
   ```

2. 安装并启动 Docker Desktop，然后在 VS Code 中依次运行任务（`Terminal > Run Task`）：

   ```text
   db: start
   db: migrate
   api: dev
   ```

3. 打开 API 文档：<http://127.0.0.1:8000/docs>。

也可以直接在终端运行：

```powershell
docker compose up -d db
uv run alembic upgrade head
uv run fastapi dev app/main.py
```

## API

| 方法 | 路径 | 用途 |
|---|---|---|
| `GET` | `/health` | 健康检查 |
| `POST` | `/tickets` | 创建工单 |
| `GET` | `/tickets` | 分页查询，可用 `status` 筛选 |
| `GET` | `/tickets/{id}` | 查询详情 |
| `PATCH` | `/tickets/{id}` | 工程师修改分类、优先级或处理状态 |
| `POST` | `/tickets/{id}/close` | 填写最终判断并关闭工单 |

创建工单示例：

```json
{
  "title": "VPN无法连接",
  "description": "认证服务器不可用，已经重启客户端",
  "user_category": "软件/VPN"
}
```

关闭工单示例：

```json
{
  "final_category": "网络/VPN",
  "final_priority": "P2",
  "resolution": "重新签发设备证书后恢复连接"
}
```

## 开发检查

```powershell
uv run ruff check .
uv run ruff format --check .
uv run pytest --cov=app
```

数据库结构由 Alembic 管理，不在应用启动时隐式建表。后续增加 AI 分析、判断记录和知识库时继续追加迁移即可。
