# Smart Gongdan（M5）

一个具备身份分流、账号生命周期管理、AI 工单理解、规则优先级、混合检索、可引用处理建议与效果评估闭环的最小工单系统：FastAPI 后端负责账号会话、工单归属、角色权限、结构化 AI 分析、可解释优先级计算、知识/历史案例检索、AI 建议和审核留痕，Vue 3 前端提供用户门户、工程师工作台和评估看板。当前阶段有意不包含公开注册、自动执行建议、自动关闭和自动派单。

## 环境要求

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Docker Desktop（用于 PostgreSQL）
- Node.js 22.12+ 与 npm 12+（用于 Vue 前端）

## 在 VS Code 中启动

1. 用 VS Code 打开本目录，并复制环境配置：

   ```powershell
   if (-not (Test-Path .env)) { Copy-Item .env.example .env }
   uv sync
   Set-Location frontend
   npm install
   Set-Location ..
   ```

2. 安装并启动 Docker Desktop，然后在 VS Code 中运行任务（`Terminal > Run Task`）：

   ```text
   app: dev
   ```

   该任务会依次等待数据库健康、应用 Alembic 迁移，再并行启动前后端。启动失败时先查看对应任务的终端输出；不要使用清空数据卷或重置数据库的方式重试。后端任务启用进程级 `PYTHONUTF8=1`，避免 Windows GBK 终端无法输出 FastAPI 启动图标。

3. 首次使用时运行 VS Code 任务 `auth: create user`，按提示创建账号。至少创建一个 `USER` 和一个 `ENGINEER` 或 `ADMIN`。

   运行 `search: seed data` 可幂等导入 15 篇示例知识和 30 条已解决历史工单。

4. 打开以下入口：

   - 统一登录入口：<http://127.0.0.1:5173/login>
   - 用户门户：<http://127.0.0.1:5173/portal/tickets/new>
   - 工程师/管理员队列：<http://127.0.0.1:5173/console/tickets>
   - 管理员账号管理：<http://127.0.0.1:5173/console/users>
   - API 文档：<http://127.0.0.1:8000/docs>

也可以直接在终端运行：

```powershell
docker compose up -d --wait db
uv run alembic upgrade head
$env:PYTHONUTF8 = '1'
uv run fastapi dev app/main.py
```

另开一个终端启动前端：

```powershell
Set-Location frontend
npm run dev
```

前端开发服务器会把 `/api` 请求代理到 `http://127.0.0.1:8000`，本地开发不需要额外配置跨域地址。

## API

| 方法 | 路径 | 用途 |
|---|---|---|
| `GET` | `/health` | 健康检查 |
| `POST` | `/auth/login` | 登录并建立 HttpOnly Cookie 会话 |
| `POST` | `/auth/logout` | 退出并撤销当前会话 |
| `GET` | `/auth/me` | 查询当前登录用户 |
| `POST` | `/users` | 管理员创建账号 |
| `GET` | `/users` | 管理员查询账号 |
| `PATCH` | `/users/{id}/status` | 管理员启用或停用账号 |
| `POST` | `/users/{id}/password/reset` | 管理员重置账号密码并撤销其会话 |
| `POST` | `/tickets` | 创建工单 |
| `GET` | `/tickets` | 服务端分页，支持 `status`、`q`、`priority`，返回筛选后总数与状态数量 |
| `GET` | `/tickets/{id}` | 查询详情 |
| `PATCH` | `/tickets/{id}` | 工程师修改分类、优先级或处理状态 |
| `POST` | `/tickets/{id}/close` | 填写最终判断并关闭工单 |
| `POST` | `/tickets/{id}/analyze` | 分析工单并保存判断、优先级事实与规则结果 |
| `GET` | `/tickets/{id}/analysis/latest` | 获取工单的最新 AI 分析 |
| `GET` | `/tickets/{id}/similar` | 获取关键词与 pgvector 合并后的 Top 5 相似结果 |
| `POST` | `/tickets/{id}/solutions/generate` | 基于最新分析和 Top 5 证据生成处理建议 |
| `GET` | `/tickets/{id}/solutions/latest` | 获取最新 AI 处理建议及人工审核结果 |
| `POST` | `/tickets/{id}/solutions/{solution_id}/review` | 工程师编辑采纳或拒绝建议 |
| `GET` | `/classification-tree` | 获取前端可用的受控分类树 |
| `POST` | `/tickets/{id}/classification/confirm` | 工程师确认分类并生成 AI/人工评估 |
| `GET` | `/tickets/{id}/judgments` | 查看用户、AI、工程师判断历史 |
| `GET` | `/metrics/classification` | 查看按工单最新确认计算的一致率 |
| `GET` | `/metrics/mvp` | 查看分类、检索、建议采纳与处理时长总览 |
| `POST` | `/metrics/search/run` | 使用版本化基准集运行并留存 Recall@5 评估 |

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
uv lock --check
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest --cov=app --cov-fail-under=90
uv pip check
uv run alembic check
Set-Location frontend
npm run quality
```

浏览器回归测试使用独立的临时数据库与测试账号，不读写开发数据库。首次执行时安装浏览器：

```powershell
Set-Location frontend
npx playwright install chromium
npm run test:e2e
```

测试会自行启动 `15173` 前端和 `18000` 测试 API，结束后关闭。请保持这两个端口空闲。GitHub Actions 分别运行后端、前端质量检查和浏览器流程回归；失败时保留截图与 trace。

### 多人处理协作

- `POST /tickets/{id}/claim` 认领并进入处理中；`POST /tickets/{id}/release` 释放负责人但保持当前状态。重复认领、重复释放、关闭后操作返回 409。
- 未认领工单保持兼容，员工仍可按原流程处理；已认领工单只能由负责人或管理员写入，其他工程师只读。管理员可释放停用账号留下的工单，再由有效工程师认领；暂不提供任意转派和自动派单。
- `TicketRead` 新增 `version` 和 `assigned_engineer_name`。所有工单写接口支持 `X-Ticket-Version` 正整数请求头，前端始终传递当前版本。旧客户端可以省略，但无法检测“打开页面后”的过期编辑；请求执行期间的并发写入仍受原子版本校验保护。
- 分析、建议生成、审核、分类确认、更新、认领、释放和关闭共用同一版本校验。AI/向量调用结束后才预占写版本，不在模型等待期间持有工单行锁；冲突返回 409，不重放写请求、不持久化部分结果。
- `GET /tickets/{id}/events?limit=100&offset=0` 仅向员工开放，按版本升序分页返回追加式操作记录（动作、操作人快照、UTC 时间、版本）；不记录工单正文，也不为旧工单补造历史操作人。
- 冲突后点击“加载最新记录”，只恢复真正修改过的字段，未修改字段使用最新默认值。如果工单已被他人关闭，原方案草稿单独展示供复制，不覆盖已保存结果。
- 本轮新增迁移 `20260907_0009`。更新已有开发环境后先运行 `uv run alembic upgrade head`；生产发布前备份并审核迁移，勿对生产库直接降级（会删除操作记录）。

并发测试 `tests/test_ticket_concurrency.py` 默认验证独立 SQLite 连接；额外设置 `TEST_DATABASE_URL` 可验证 PostgreSQL。为避免误用开发库，数据库名必须为专用的 `smartgongdan_test_concurrency`，测试会创建并清理该库中的测试表，**不要放入任何业务数据**。CI 自动创建独立测试库并执行这组测试；不把 SQLite 通过视为 PostgreSQL 已验证。

## 试用流程与草稿保护

- 用户提交后可进入 `/portal/tickets/{id}` 查看完整问题、当前状态和最终解决方案；后端校验工单归属。
- 用户和员工列表均使用服务端分页，可搜索标题或 `INC-0001` 编号。员工还可筛选优先级；优先采用人工最终优先级，再回退到规则优先级。
- `status_counts` 根据当前用户权限、搜索和优先级统计，不受当前状态按钮或分页影响；`total` 则是当前全部筛选条件下的总数。
- 列表筛选与页码保存在 URL 中，从详情返回可回到原列表位置。
- 重新分析保留工程师手工调整的最终分类、优先级和解决方案。关闭前显示确认提示；页面内进行中的写操作互斥，过期请求不能覆盖另一张工单。
- 工单填写与处理草稿仅存于当前标签页内存，按账号和工单隔离；会话过期后同一账号重新登录可恢复。主动退出或切换账号会清除草稿，刷新／关闭标签页也会丢失；离开时会提示。
- 重新登录后不会自动重放创建、分析或关闭请求，需要用户确认后再次提交。

完整工程边界和不变量见 [项目契约](docs/PROJECT_CONTRACT.md)，参与开发前请阅读 [开发约定](CONTRIBUTING.md)。当前状态记录在 [开发交接包](docs/HANDOFF.md)，剩余风险按 [稳定化待办](docs/STABILIZATION_BACKLOG.md) 管理。VS Code 可直接运行 `quality: all` 任务执行前后端同一组门禁。

## 前端结构与界面规范

```text
frontend/src/
├─ api/          HTTP 契约、类型和错误处理
├─ components/   可复用状态与品牌组件
├─ layouts/      用户端 Portal 与管理员 Console 框架
├─ styles/       全局设计令牌和基础样式
└─ views/        按角色与业务流程组织的页面
```

- 中性浅灰画布、白色内容面和单一品牌蓝构成主视觉；AI 仅用克制的紫色标识。
- 用户端采用顶部导航与 720px 聚焦表单，优先降低填写负担。
- 管理员端采用 224px 侧栏和 7:5 双栏工作台，右侧处理表单在桌面端保持可见。
- 所有业务操作均调用已有 FastAPI，不在前端模拟 AI 结果或工单状态。

数据库结构由 Alembic 管理，不在应用启动时隐式建表。后续增加 AI 分析、判断记录和知识库时继续追加迁移即可。

## M1 AI 配置

默认使用确定性的本地分析器，便于无 API Key 开发和测试：

```dotenv
AI_PROVIDER=local
AI_MODEL=local-rules-v1
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=local-hash-v1
EMBEDDING_DIMENSIONS=128
```

要连接支持 OpenAI Chat Completions 与 JSON Schema 的兼容接口，修改 `.env`：

```dotenv
AI_PROVIDER=openai_compatible
AI_MODEL=your-model-name
AI_BASE_URL=https://your-provider.example/v1
AI_API_KEY=your-secret
```

`AIService` 是独立适配边界。API 路由只接收已经验证的 `TicketAIAnalysis`，分类与二级分类必须来自预定义分类树；无法判断时回退到 `其他 / 未分类`。每次重新分析都会追加历史记录，不覆盖之前的分析。

当使用 `openai_compatible` 时，分析和建议请求会在发送前创建脱敏副本，替换常见邮箱、手机号、网络地址、设备标识、用户目录和显式凭据；本地工单与审计记录保持原值。完整边界和供应商上线门槛见 [AI 出站数据策略](docs/AI_DATA_POLICY.md)。

项目包含 30 条带人工分类标签的 M1 模拟工单。运行本地基线评估：

```powershell
uv run python -m scripts.evaluate_ai
```

也可以运行 VS Code 任务 `evaluation: classification pilot`，或直接执行：

```powershell
uv run python -m scripts.evaluate_ai --pilot
```

该命令读取版本化清单 `data/pilot_classification_manifest.json`，将 30 条基础样例分别转换为原始、服务台描述、脱敏上下文和结构化表单四种表达，共 120 条确定性鲁棒性样例，并按分类输出分层结果。它只能验证同一语义在受控格式变化下是否稳定，不能当作 120 条独立真实工单的分类准确率。真实模型上线前仍需使用 100～500 条经授权、人工脱敏并独立复核标签的真实工单评测。

## M1.5 评估口径

- 每次工程师确认都会追加一条 `ENGINEER` 判断，不覆盖历史。
- 如果已有 AI 判断，确认时会与最新一条 AI 判断生成不可变评估记录。
- `category_agreement_rate` 表示一级分类一致率。
- `exact_agreement_rate` 表示一级、二级分类均一致的比例。
- 全局指标按每张工单的最新人工确认统计，避免重复确认让单张工单获得更高权重。
- 没有 AI 分析的人工确认正常留痕，但不进入一致率分母。

## M1.7 身份与账号管理

- `USER` 登录后进入用户门户，只能查询自己提交的工单。
- `ENGINEER` 登录后进入工单队列，可以分析、确认分类、更新和关闭工单。
- `ADMIN` 复用工程师工作台，并可在 `/console/users` 创建、启停账号和重置他人密码。
- 会话使用随机不透明令牌；数据库只保存 SHA-256 摘要，浏览器通过 HttpOnly Cookie 携带原始令牌。
- 密码使用 pwdlib 推荐的 Argon2 哈希，不保存或记录明文。
- 停用账号或由管理员重置密码时，会在同一事务内撤销该账号的全部会话。
- 管理员不能在账号管理接口中停用自己或重置自己的密码，避免误锁定当前管理会话。
- 当前不开放自助注册。首次管理员使用 `auth: create user` VS Code 任务创建，后续账号可在管理页面维护。

## M2 可解释优先级

- AI 只提取 `impact`、`urgency` 和 `affected_scope`，不直接决定 P1–P4。
- 规则服务按 `影响分 × 50% + 紧急度分 × 30% + 范围分 × 20%` 计算总分。
- 总分 `≥80` 为 P1，`≥60` 为 P2，`≥30` 为 P3，其余为 P4。
- 每次分析会追加保存事实、三个分项分数、总分与当次规则结果；旧分析不会被覆盖或补写虚构事实。
- 工单的 `ai_priority` 保存最新分析的规则结果，工程师仍可在关闭工单时确认最终优先级。
- 工程师工作台展示完整计算依据，明确区分“AI 提取事实”和“规则计算等级”。

## M3 知识与历史案例检索

- `knowledge` 保存知识条目、受控分类、嵌入模型和 128 维向量。
- 已关闭工单保存标题、问题、分类和解决结果的检索向量；关闭工单时与业务变更同一事务写入。
- 关键词查询和 pgvector 余弦近邻查询各自获取候选，再使用固定的倒数排名融合进行去重和 Top 5 排序。
- 默认 `local-hash-v1` 是无需密钥的确定性开发嵌入器；它用于验证完整检索链路，不代表生产语义模型效果。
- 工程师工作台展示知识或历史工单来源、匹配方式、综合匹配度和已有解决结果。
- 运行 `uv run python -m scripts.seed_search_data` 可重复导入样本；知识会刷新，历史工单不会重复或覆盖。

## M4 检索增强处理建议

- 生成输入固定包含当前工单、最新 AI 分析、用户已尝试操作和 Top 5 混合检索证据。
- 模型引用必须来自本次检索结果；服务层会拒绝虚构引用，并过滤与用户已尝试操作重复的步骤。
- 每次重新生成都会追加 `ticket_ai_solutions` 记录，不覆盖历史建议。
- 工程师可以编辑后采纳或填写原因拒绝；审核记录单独保存且同一建议只能审核一次。
- 采纳只会把文本填入最终解决方案草稿，不会执行操作、修改状态或自动关闭工单。

## M5 效果评估

- `/console/evaluation` 集中展示分类完全一致率、Recall@5、建议采纳率和真实工单平均处理时长。
- 建议采纳率以已完成人工审核的建议为分母；待审核建议单独展示，不稀释结果。
- 拒绝建议时记录受控原因类型与补充说明，便于区分证据不匹配、重复步骤和风险问题。
- Recall@5 使用 `data/search_evaluation.json` 中带版本号的基准集；每次运行追加保存模型、得分和逐条结果。
- 处理时长只统计用户实际提交并关闭的工单，导入的历史检索案例不进入指标。
- 可在评估看板点击运行，也可执行 `uv run python -m scripts.evaluate_search`；本地基准当前为 14 条查询。
