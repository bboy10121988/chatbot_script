# 关键词 Chatbot 商品推荐对话框 — 后端

最小可运行 Flask 骨架，包含：多租户、API Key 鉴权、基础限流、关键词匹配推荐、购物车与商品接口，以及可嵌入的 `embed.js`。

## 目录结构

```
app/
  __init__.py            # app factory, 注册蓝图与错误处理
  config.py              # 配置（环境变量）
  extensions.py          # SQLAlchemy、Migrate、Redis 初始化
  models.py              # 数据模型（与 db/schema.sql 对齐）
  auth.py                # API Key 鉴权与 CORS 校验
  ratelimit.py           # Redis/in-memory 限流
  services/recommendation.py  # 关键词匹配与检索兜底
  routes/
    health.py
    products.py
    cart.py
    chat.py
    static.py            # /embed.js 静态脚本
public/
  embed.js               # 前端浮窗最小示例
db/
  schema.sql             # MySQL 初始 DDL
wsgi.py                  # 入口
requirements.txt         # 依赖
.env.example             # 环境变量示例
```

## 本地运行

1. 准备环境
- Python 3.11+
- MySQL 8（或先用 SQLite 方便本地验证）
- Redis（可选，用于限流）

2. 安装依赖
```
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

3. 配置数据库
- 方案 A（推荐）：在 MySQL 中执行 `db/schema.sql`
- 方案 B（本地便捷）：将 `.env` 中的 `DATABASE_URL` 改为 `sqlite:///chatbot.db`

4. 启动服务
```
python wsgi.py
# 服务默认监听 http://127.0.0.1:5000
```

## Render + Supabase 部署（推荐）

1) Supabase（PostgreSQL）
- 创建项目 → 进入 Project Settings → Database → 复制 Connection string（URI）
- 将前缀改成 SQLAlchemy 支持的：`postgresql+psycopg2://...`

2) Render（后端 API）
- 连接本仓库，创建 Web Service
- Build: `pip install -r requirements.txt`
- Start: `gunicorn 'wsgi:app' --workers 2 --threads 4 --bind 0.0.0.0:$PORT --timeout 60`
- Health Check Path: `/health`
- 环境变量：
  - `FLASK_ENV=production`
  - `SECRET_KEY=<随机字符串>`
  - `DATABASE_URL=postgresql+psycopg2://<user>:<pass>@<host>:<port>/<db>`（来自 Supabase）
  - `CORS_ALLOWED_ORIGINS=https://<your-gh-username>.github.io`
  - `AUTO_BOOTSTRAP=true`
  - `SITE_TENANT_NAME=demo`
  - `SITE_API_KEY=<你的站点API Key>`
  - `BOOTSTRAP_SAMPLE_DATA=true`

3) GitHub Pages（管理页/嵌入测试）
- 打开 `index.html` 所在仓库的 GitHub Pages
- 访问 `https://<your-gh-username>.github.io/<repo>/`
- 顶部“API 设置”：
  - API Base：填 `https://<你的 Render 服务域名>`（无需 `/v1`，页面会自动补）
  - API Key：填上面 `SITE_API_KEY`
  - 点击“测试后端连线”，显示 `/health OK` 与 `/v1/settings OK` 即通

4) 嵌入到真实站点
```
<script>
  window.CHATBOT_API_BASE = 'https://<your-render-domain>/v1';
  window.CHATBOT_API_KEY = '<SITE_API_KEY>';
</script>
<script src="https://<your-render-domain>/embed.js"></script>
```

---

## GitHub Pages（前端/管理页）
- 启用 Pages 指向仓库根目录
- 在 `index.html` 中设置：
  - `window.CHATBOT_API_BASE='https://<your-render-domain>/v1'`
  - `window.CHATBOT_API_KEY='<your_site_api_key>'`
- 后端 CORS 白名单加入 Pages 域名

## 准备数据与 API Key

在数据库中插入一个租户、API Key（bcrypt 哈希）、商品与关键词规则。例如（MySQL）：

```sql
INSERT INTO tenants (name) VALUES ('demo');
SET @tenant := LAST_INSERT_ID();

-- 生成密钥哈希（Python 示例）
-- >>> import bcrypt; bcrypt.hashpw(b"demo_key", bcrypt.gensalt())
-- 将生成的二进制哈希写入 api_keys.key_hash 字段
INSERT INTO api_keys (tenant_id, key_hash, label, rate_limit_rpm, is_active) VALUES
(@tenant, UNHEX(REPLACE('2432622431322463746e4c4a7a...','0x','')), 'demo', 60, 1);

INSERT INTO products (tenant_id, name, price, currency, image_url, stock, is_active, tags)
VALUES
(@tenant, '真无线蓝牙耳机', 299.00, 'CNY', 'https://cdn.example.com/p1.jpg', 100, 1, JSON_ARRAY('蓝牙','耳机')),
(@tenant, '有线入耳式耳机', 59.00, 'CNY', 'https://cdn.example.com/p2.jpg', 200, 1, JSON_ARRAY('有线','耳机'));

INSERT INTO keyword_rules (tenant_id, trigger_text, match_type, priority, product_ids, response_text, is_active)
VALUES
(@tenant, '蓝牙耳机', 'contains', 100, JSON_ARRAY(1), '为你推荐以下蓝牙耳机：', 1);
```

注意：`api_keys.key_hash` 需写入 bcrypt 结果的原始字节；如使用 SQL 直接插入，确保以 `BLOB/VARBINARY` 方式写入。

## 调用接口

- `POST /v1/chat/message`
```
curl -X POST http://127.0.0.1:5000/v1/chat/message \
  -H 'X-API-Key: demo_key' -H 'Content-Type: application/json' \
  -d '{"message":"我想買藍牙耳機"}'
```

- `POST /v1/cart/items`
```
curl -X POST http://127.0.0.1:5000/v1/cart/items \
  -H 'X-API-Key: demo_key' -H 'Content-Type: application/json' \
  -d '{"conversation_id":1, "product_id":1, "quantity":1}'
```

## 前端嵌入

将 `/embed.js` 以 `<script src="https://your-domain/embed.js" ...>` 引入页面，或本地：
```
<script>
  window.CHATBOT_API_BASE = 'http://127.0.0.1:5000/v1';
  window.CHATBOT_API_KEY = 'demo_key';
</script>
<script src="http://127.0.0.1:5000/embed.js"></script>
```

## 后续
- 接入 Alembic 迁移（当前以 schema.sql 初始化）
- 完善规则管理后台与鉴权模型（Key 前缀/ID 以提升查询效率）
- 引入更好的中文分词与搜索（ES/Meilisearch）
- 增强安全（请求签名、细化 CORS 白名单、多维限流）
