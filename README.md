# 基于 RAG 的电商商家 AI 客服导购系统 MVP

这是一个面向中小网购平台商家的本地可演示 MVP。商家上传商品表格和店铺规则后，系统会把资料保存到 SQLite，并用本地 embedding 模型写入 Chroma 向量库。顾客咨询商品推荐、尺码、材质等导购问题时，系统会优先做结构化商品筛选并返回商品卡片；咨询发货、退换货、售后等规则问题时，系统会做 RAG 检索；咨询模拟订单时会查询本地订单表；发起退货、退款、投诉等售后问题时会自动创建售后工单。

本项目不做 AI 商品文案生成、不做评论/差评分析、不做支付系统，也不接入真实淘宝、拼多多、抖店等平台。

## 核心功能

- 商家登录：固定测试账号 `admin / 123456`
- 商品管理：上传 CSV / Excel，解析商品字段，保存到 SQLite，并写入 Chroma
- 知识库管理：上传 TXT / Markdown 店铺规则，自动切分文本并写入 Chroma
- AI 客服测试：商家模拟顾客提问，查看回答、`mode`、命中来源和来源摘要
- 顾客端预览：模拟真实网购平台客服聊天窗口，不展示调试信息
- RAG 约束：回答基于上传资料；无资料时提示联系人工客服；来源去重，最多展示 3 条
- 推荐约束：商品推荐最多 3 个；规则问题优先规则，商品问题优先商品
- 结构化商品导购：推荐、预算、类目、人群、场景、尺码、材质、库存等问题先走 SQLite 商品筛选
- 商品卡片展示：`/api/chat` 返回 `product_cards`，AI 客服测试页和顾客端都会展示商品卡片
- 商品对比：支持“防晒衬衫和通勤托特包有什么区别”“159 的衬衫和 189 的包怎么选”等对比问题
- 模拟订单查询：本地 `orders` 表内置示例订单，支持订单状态、物流状态、快递单号查询
- 售后工单系统：退货、换货、退款、质量问题、物流问题、投诉等会自动创建售后工单
- 聊天记录管理：每次 `/api/chat` 调用都会保存问题、回答、来源、mode 和人工处理状态
- 未命中问题收集：RAG 未命中或回答无资料时自动进入待处理列表
- 人工客服接管：识别“人工、客服、投诉、退款失败、急、没解决”等问题并标记需要人工处理

## 技术栈

- 前端：静态 React，由 FastAPI 托管，不需要单独 npm 启动
- 后端：FastAPI
- 数据库：SQLite
- 向量数据库：Chroma
- 聊天模型：DeepSeek API，使用 OpenAI 兼容 chat/completions 调用方式
- 向量模型：本地 `sentence-transformers`，默认 `BAAI/bge-small-zh-v1.5`
- 文件解析：`pandas`、`openpyxl`

## 项目结构

```text
backend/app/
  main.py          FastAPI 路由入口和静态页面托管
  config.py        DeepSeek、本地 embedding、数据库路径配置
  database.py      SQLite 初始化、商品和知识文件读写
  file_parser.py   CSV/Excel/TXT/Markdown 解析与文本切分
  rag.py           本地 embedding、Chroma 写入、检索、来源去重
  product_guide.py 商品条件解析、结构化筛选、商品卡片和对比匹配
  order_service.py 订单查询和售后工单意图解析、卡片转换
  chat_service.py  RAG 上下文组装与 DeepSeek 回答生成
  schemas.py       请求参数模型
frontend/
  index.html       前端入口
  app.js           页面和交互逻辑
  styles.css       UI 样式
  vendor/          本地 React 运行时
samples/
  products_sample.csv       示例商品数据
  orders_sample.csv         示例订单数据
  store_rules_sample.txt    示例店铺规则
requirements.txt            Python 依赖
.env.example                环境变量模板
```

## 环境变量配置

复制模板：

```bash
cp .env.example .env
```

编辑 `.env`：

```env
DEEPSEEK_API_KEY=你的 DeepSeek API Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
CHAT_MODEL=deepseek-v4-flash
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5
CHROMA_DB_PATH=./data/chroma
SQLITE_DB_PATH=./data/app.db
```

说明：

- `DEEPSEEK_API_KEY`：必填，DeepSeek 控制台获取。
- `DEEPSEEK_BASE_URL`：固定使用 `https://api.deepseek.com`。
- `CHAT_MODEL`：默认 `deepseek-v4-flash`；如果账号暂不支持，也可以改成 `deepseek-chat`。
- `EMBEDDING_PROVIDER`：保持 `local`，本项目不调用远程 embedding API。
- `EMBEDDING_MODEL`：默认中文向量模型 `BAAI/bge-small-zh-v1.5`。
- `CHROMA_DB_PATH` / `SQLITE_DB_PATH`：本地演示数据存储路径。

## 本地启动步骤

进入项目目录：

```bash
cd /Users/mac/Documents/Codex/2026-06-04/rag-ai-mvp-1-ai-2/outputs/rag-merchant-ai-cs
```

创建环境并安装依赖：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

启动后端和前端页面：

```bash
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

前端不需要单独启动。浏览器访问：

```text
http://127.0.0.1:8000
```

## 测试账号

```text
账号：admin
密码：123456
```

## 示例数据说明

`samples/products_sample.csv` 包含 4 个演示商品：

- 轻薄防晒衬衫
- 通勤托特包
- 男士速干运动 T 恤
- 儿童纯棉短裤

字段包含：商品名称、类目、价格、尺码、材质、适用人群、商品卖点、库存、商品链接。

`samples/store_rules_sample.txt` 包含店铺规则：

- 发货规则
- 运费规则
- 退换货规则
- 尺码建议
- 质量问题售后
- 常见问题 FAQ

`samples/orders_sample.csv` 包含 5 条本地模拟订单，启动后会自动写入 SQLite：

- `10001`：轻薄防晒衬衫，已发货，运输中
- `10002`：通勤托特包，已付款，待发货
- `10003`：轻薄防晒衬衫，已完成，已签收
- `10004`：通勤托特包，已签收，售后申请中
- `10005`：其他商品，已取消，未发货

## 从零验证流程

1. 按上面的步骤创建 `.env`、安装依赖并启动服务。
2. 打开 `http://127.0.0.1:8000`。
3. 使用 `admin / 123456` 登录。
4. 进入“商品管理”，上传 `samples/products_sample.csv`。
5. 确认商品列表出现 4 条商品。
6. 进入“知识库管理”，上传 `samples/store_rules_sample.txt`。
7. 确认知识文件列表出现该文件，并显示 chunk 数。
8. 进入“AI 客服测试”，输入问题并查看回答、`mode`、来源和摘要。
9. 进入“订单管理”，查看本地模拟订单和物流状态。
10. 进入“售后工单”，查看 AI 自动创建的售后工单，并尝试修改工单状态。
11. 进入“聊天记录”，确认刚才的问题、回答、mode、订单卡片和工单卡片已经保存。
12. 进入“未命中问题”，查看知识库无法回答的问题，并可标记为已处理。
13. 进入“顾客端预览”，用聊天窗口模拟真实顾客咨询。

推荐测试问题：

- 多久发货？
- 可以退货吗？
- 有适合学生党的商品吗？
- 质量问题怎么处理？
- 有 200 元以内的包推荐吗？
- 有没有适合夏天通勤的商品？
- 轻薄防晒衬衫适合什么人？
- 防晒衬衫和通勤托特包有什么区别？
- 有 100 元以内的包吗？
- 订单 10001 发货了吗？
- 我的订单 10002 到哪了？
- 订单 10003 签收了吗？
- 查询订单 99999
- 订单 10003 商品有质量问题，我要退货
- 我要退款，订单号 10004
- 我要投诉，物流一直没更新
- 商品破损了怎么办？
- 你们支持海外配送吗？
- 我要找人工客服

## DeepSeek 调用验证方法

先检查健康接口：

```bash
curl http://127.0.0.1:8000/api/health
```

确认返回中：

```json
{
  "deepseek_chat_configured": true,
  "deepseek_base_url": "https://api.deepseek.com"
}
```

再调用聊天接口：

```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"多久发货？","top_k":5}'
```

如果返回：

```json
"mode": "deepseek_openai_compatible"
```

说明 DeepSeek 已成功调用。

其他 mode 含义：

- `local_fallback_no_deepseek_key`：没有配置 `DEEPSEEK_API_KEY`
- `local_fallback_after_deepseek_error`：DeepSeek 调用失败，后端临时用检索摘要兜底
- `no_context`：知识库没有检索到相关内容

## 新增管理接口

聊天记录：

- `GET /api/chat/sessions`
- `GET /api/chat/history?session_id=xxx`
- `GET /api/chat/records`
- `GET /api/chat/records?filter=human`
- `GET /api/chat/records?filter=deepseek`
- `GET /api/chat/records?filter=fallback`

未命中问题：

- `GET /api/missed-questions`
- `PATCH /api/missed-questions/{id}/resolve`

商品导购辅助接口：

- `GET /api/products/search?keyword=&category=&max_price=&target_user=`
- `GET /api/products/{id}`

模拟订单：

- `GET /api/orders`
- `GET /api/orders/search?keyword=`
- `GET /api/orders/{order_no}`

售后工单：

- `GET /api/aftersales`
- `GET /api/aftersales?status=pending`
- `GET /api/aftersales/{id}`
- `POST /api/aftersales`
- `PATCH /api/aftersales/{id}/status`

`/api/chat` 会额外返回：

```json
{
  "session_id": "customer-xxx",
  "user_type": "customer",
  "needs_human": false,
  "is_fallback": false,
  "record_id": 1,
  "product_cards": [
    {
      "id": 1,
      "name": "轻薄防晒衬衫",
      "category": "女装/衬衫",
      "price": "159",
      "size": "S/M/L/XL",
      "material": "锦纶混纺防晒面料",
      "target_user": "上班族/学生党/夏季通勤",
      "selling_points": "UPF50+ 防晒；版型宽松；可外搭；适合夏天通勤和日常出行",
      "stock": "86",
      "link": "https://example.com/products/sun-shirt"
    }
  ],
  "order_card": {
    "order_no": "10001",
    "customer_name": "小林",
    "product_name": "轻薄防晒衬衫",
    "order_status": "已发货",
    "shipping_status": "运输中",
    "tracking_no": "ZT123456789",
    "express_company": "中通快递",
    "paid_amount": "159",
    "created_at": "2026-06-01T10:20:00",
    "shipped_at": "2026-06-02T14:30:00",
    "aftersale_status": "无售后"
  },
  "aftersale_ticket": {
    "id": 1,
    "ticket_no": "AS202606041200000001",
    "order_no": "10003",
    "issue_type": "质量问题",
    "issue_description": "订单 10003 商品有质量问题，我要退货",
    "status": "pending",
    "needs_human": true,
    "created_at": "2026-06-04T12:00:00"
  }
}
```

前端“AI 客服测试”页会显示 `mode`；顾客端不会显示调试信息。如果 `needs_human=true`，顾客端会显示“已转人工处理”。

商品推荐类问题会返回 `product_cards`；发货、退货、售后等规则问题不会返回商品卡片。没有符合条件的商品时，系统会回答“目前店铺资料中暂时没有找到完全符合条件的商品，建议联系人工客服确认。”并记录到未命中问题。

订单查询类问题会返回 `order_card`；售后申请、退款、投诉、质量问题等会创建 `aftersale_ticket`，并设置 `needs_human=true`。如果订单号不存在，系统会回答“没有查询到该订单，建议确认订单号是否正确，或联系人工客服处理。”

## 常见问题处理

### 首次上传商品或知识文件很慢

首次使用本地 embedding 时会下载 `BAAI/bge-small-zh-v1.5`，可能需要几分钟。下载完成后会缓存到本机，后续会快很多。

### `ModuleNotFoundError: No module named 'fastapi'`

依赖没有安装，执行：

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### `ModuleNotFoundError: No module named 'sentence_transformers'`

本地 embedding 依赖没有安装，执行：

```bash
pip install -r requirements.txt
```

### 上传 Excel 失败

Excel 解析依赖 `openpyxl`。确认文件格式是 `.xlsx` 或 `.xls`，并重新安装依赖：

```bash
pip install -r requirements.txt
```

### DeepSeek 调用失败

检查 `.env`：

- `DEEPSEEK_API_KEY` 是否填写
- `DEEPSEEK_BASE_URL` 是否为 `https://api.deepseek.com`
- `CHAT_MODEL` 是否为账号支持的模型，例如 `deepseek-v4-flash` 或 `deepseek-chat`

然后重启后端。

### Chroma 维度不一致

如果修改过 `EMBEDDING_MODEL`，旧向量可能不能复用。删除运行数据后重新上传：

```bash
rm -rf data/chroma data/app.db
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

## 项目演示流程

适合录屏或答辩时按顺序展示：

1. 打开首页，说明这是“基于 RAG 的电商商家 AI 客服导购系统”。
2. 使用 `admin / 123456` 登录商家后台。
3. 进入“商品管理”，上传 `samples/products_sample.csv`，展示商品列表。
4. 说明商品资料会保存到 SQLite，并同步写入 Chroma 向量库。
5. 进入“知识库管理”，上传 `samples/store_rules_sample.txt`，展示知识文件列表。
6. 说明规则文本会自动切分 chunk，并使用本地 embedding 写入 Chroma。
7. 进入“AI 客服测试”，依次提问：
   - `多久发货？`
   - `可以退货吗？`
   - `有适合学生党的商品吗？`
   - `有 200 元以内的包推荐吗？`
   - `有没有适合夏天通勤的商品？`
   - `轻薄防晒衬衫适合什么人？`
   - `防晒衬衫和通勤托特包有什么区别？`
   - `有 100 元以内的包吗？`
   - `订单 10001 发货了吗？`
   - `我的订单 10002 到哪了？`
   - `订单 10003 签收了吗？`
   - `查询订单 99999`
   - `订单 10003 商品有质量问题，我要退货`
   - `我要退款，订单号 10004`
   - `我要投诉，物流一直没更新`
   - `商品破损了怎么办？`
   - `质量问题怎么处理？`
   - `你们支持海外配送吗？`
   - `我要找人工客服`
8. 展示商品推荐回答下方的商品卡片，说明系统先做结构化商品筛选，再生成导购回复。
9. 展示规则类回答下方的来源，说明发货、退货、售后问题仍然基于知识库资料回答。
10. 展示订单查询回答下方的订单卡片，说明系统只基于本地 `orders` 表回答订单和物流状态。
11. 展示售后问题自动生成的售后工单卡片，说明退款、投诉、质量问题会进入人工处理队列。
12. 指出测试页的 `mode=deepseek_openai_compatible`，证明 DeepSeek 调用成功。
13. 进入“订单管理”，搜索 `10001` 或 `托特包`，展示订单详情。
14. 进入“售后工单”，按状态筛选工单，并演示把工单从 `pending` 改为 `processing` 或 `resolved`。
15. 进入“聊天记录”，切换筛选：
    - 全部
    - 需要人工处理
    - DeepSeek 成功
    - fallback
16. 进入“未命中问题”，展示“海外配送”或“订单 99999”等无法回答的问题，并演示标记为已处理。
17. 进入“顾客端预览”，询问 `订单 10001 发货了吗？` 或 `我要找人工客服`，展示订单卡片或“已转人工处理”提示。
18. 总结系统边界：当前是本地 MVP，不做支付、不接真实电商平台、不做评论分析。
