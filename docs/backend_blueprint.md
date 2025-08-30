# 关键词 Chatbot 商品推荐对话框 — 后端蓝图草案

## 概览
- 目标：提供可嵌入任意网页的客服对话浮窗，基于关键词触发商品推荐卡片，并支持“加入购物车”。
- 技术栈：Flask（API）、MySQL（数据）、Redis（会话/限流/缓存，可选）、Nginx（反向代理/CORS）、Alembic（迁移）。
- 特性：多租户（站点级 API Key）、关键词规则驱动、简易对话态、基础鉴权与限流、可扩展的推荐与检索。

## 架构
- 前端嵌入：站点引入 `embed.js` 生成悬浮按钮与对话框；与后端通过 HTTPS 交互（站点携带租户 API Key）。
- 后端服务：Flask 提供 REST API；关键词匹配引擎与推荐服务在应用层实现；对接 Redis 做限流/会话缓存。
- 数据存储：MySQL 存储商品、关键词规则、会话消息、购物车等核心数据。
- 数据流（简述）：
  1) 用户点击悬浮按钮 → 打开对话框
  2) 输入文本 → 前端调用 `POST /v1/chat/message`
  3) 后端：分词/归一化 → 同义词扩展 → 规则匹配 → 商品检索/重排
  4) 返回：机器人文本 + 商品卡片数组
  5) 用户点“加入购物车” → `POST /v1/cart/items` → 返回购物车快照

## 数据库设计（MySQL）
- 多租户：所有业务表带 `tenant_id`；通过站点的 `api_keys` 与 `tenants` 绑定。
- 主要表：
  - `tenants`：租户与站点管理。
  - `api_keys`：站点访问后端的 API Key（哈希存储）。
  - `products`：商品基础信息（支持 JSON 标签）。
  - `keyword_rules`：关键词触发规则（匹配类型、优先级、本地化、对应商品、可选回应文本）。
  - `synonyms`：同义词（便于规则泛化）。
  - `conversations`/`messages`：会话与消息存档（简单对话态）。
  - `carts`/`cart_items`：购物车与商品明细。

建议使用 MySQL 8.0（支持 JSON 与更佳索引策略）。DDL 见 `db/schema.sql`。

## API 设计（v1）
- 鉴权：`X-API-Key: <key>`（对应 `api_keys`），后端按 `Origin` 校验 CORS（与租户域名/白名单匹配）。
- 错误模型：`{ "error": { "code": "string", "message": "string" } }`；2xx 为成功，4xx/5xx 携带错误对象。

1) 接收用户消息并返回推荐
- `POST /v1/chat/message`
  - 请求：
    ```json
    {
      "conversation_id": "optional-string",
      "message": "我想买蓝牙耳机",
      "locale": "zh-CN",
      "metadata": {"page": "/product/123"}
    }
    ```
  - 响应：
    ```json
    {
      "conversation_id": "abc123",
      "messages": [
        {"role": "assistant", "type": "text", "content": "为你找到以下商品："}
      ],
      "products": [
        {
          "id": "p_1001",
          "name": "真无线蓝牙耳机",
          "image_url": "https://cdn.example.com/p_1001.jpg",
          "price": {"value": 299.00, "currency": "CNY"},
          "tags": ["蓝牙", "降噪"],
          "add_to_cart": {"product_id": "p_1001", "default_qty": 1}
        }
      ]
    }
    ```

2) 加入购物车
- `POST /v1/cart/items`
  - 请求：
    ```json
    {
      "conversation_id": "abc123",
      "product_id": "p_1001",
      "quantity": 1
    }
    ```
  - 响应（购物车快照）：
    ```json
    {
      "cart_id": "c_789",
      "status": "open",
      "items": [
        {"product_id": "p_1001", "name": "真无线蓝牙耳机", "quantity": 1, "unit_price": 299.00, "currency": "CNY"}
      ],
      "total": {"value": 299.00, "currency": "CNY"}
    }
    ```

3) 获取商品（可选调试或前端补全）
- `GET /v1/products/:id`、`GET /v1/products?ids=...`（返回卡片所需最小字段）。

## 关键词匹配与推荐逻辑
- 预处理：
  - 文本归一化（小写、去标点、全半角统一）；中文分词（可选：jieba/结巴；后续替换为 ICU 分词或服务化）。
  - 同义词扩展：根据 `synonyms` 表对分词结果进行扩展。
- 匹配策略（按优先级）：
  1) 规则精确匹配（`exact`）
  2) 前缀/包含匹配（`prefix`/`contains`）
  3) 正则匹配（`regex`，慎用、配限额）
  4) 兜底检索：基于产品 `name`/`tags` 的 LIKE/INSTR 或全文索引（中文可先用规则+标签；中长期引入 ES/Meilisearch）
- 结果重排：
  - 依据规则优先级、热度（销量/点击）、库存、价格带、相似度分数进行加权；支持多样性（去重品牌/类目）。
  - 输出限制：默认返回 3–5 个商品卡片。

## 对话与状态
- `conversations` 记录会话，`messages` 记录来回轮次；后端返回 `conversation_id`，前端持久化到 localStorage。
- 简单机器人文案：支持在 `keyword_rules.response_text` 配置辅助提示；后续可接入 LLM 生成文案并用规则约束结果。

## 安全与合规
- 鉴权：`X-API-Key` 必填；仅允许来自绑定域名的 `Origin`（服务端维护 CORS 白名单）。
- 限流：基于 Redis 按 API Key 和 IP 维度（默认 60 req/min；敏感端点更低）。
- 输入校验：长度限制、正则白名单、JSON schema 校验（pydantic/Marshmallow）。
- 数据隔离：所有查询按 `tenant_id` 过滤；API Key→租户映射。
- 日志与审计：记录请求 ID、租户、路径、限流命中、写操作审计。

## 可扩展性
- 规则管理后台（后续）：可视化增删改查、优先级拖拽、批量导入。
- 同义词/类目词库：按语言与租户维护，热词自动挖掘。
- 搜索引擎：迁移至 ES/Meilisearch 以提升召回与排序质量。
- 推荐：加入协同过滤/向量召回，多路召回+融合排序。

## 部署与配置
- 形态：Docker（Flask + Gunicorn/Uvicorn workers）、MySQL、Redis、Nginx。
- 配置：
  - `DATABASE_URL`、`REDIS_URL`、`CORS_ALLOWED_ORIGINS`、`DEFAULT_RATE_LIMIT`、`LOG_LEVEL`。
  - `API_KEY_HASH_ALGO`（如 `argon2`/`bcrypt` 存储哈希）。
- 迁移：Alembic 管理（初始脚本参考 `db/schema.sql`）。
- 监控：
  - 指标：QPS、p95 延迟、限流命中率、商品命中率、购物车转化率。
  - 报警：5xx 激增、数据库连接池耗尽。

## 前端嵌入脚本（最小示例）
```html
<script>
  (function(){
    const API_BASE = "https://api.example.com/v1";
    const API_KEY = "<your-site-api-key>";
    const btn = document.createElement('button');
    btn.innerText = '聊天咨询';
    btn.style = 'position:fixed;right:24px;bottom:24px;z-index:9999;padding:10px 14px;border-radius:20px;background:#1f8fff;color:#fff;border:none;cursor:pointer;';
    document.body.appendChild(btn);
    const panel = document.createElement('div');
    panel.style = 'position:fixed;right:24px;bottom:72px;width:340px;height:480px;background:#fff;border:1px solid #e5e7eb;border-radius:12px;box-shadow:0 10px 30px rgba(0,0,0,.1);display:none;z-index:9999;overflow:hidden;';
    panel.innerHTML = '<div id="chat" style="height:100%;display:flex;flex-direction:column">\
      <div id="msgs" style="flex:1;overflow:auto;padding:12px"></div>\
      <div style="display:flex;border-top:1px solid #eee">\
        <input id="inp" style="flex:1;padding:10px;border:0;outline:none" placeholder="说点什么..."/>\
        <button id="send" style="padding:0 12px;border:0;background:#1f8fff;color:#fff">发送</button>\
      </div></div>';
    document.body.appendChild(panel);
    let conversationId = localStorage.getItem('cb_conversation_id') || null;
    btn.onclick = () => panel.style.display = panel.style.display==='none'?'block':'none';
    const msgs = () => document.getElementById('msgs');
    const addMsg = (who, text) => { const d=document.createElement('div'); d.style='margin:6px 0;font-size:14px;'; d.textContent=(who==='user'?'我: ':'机器人: ')+text; msgs().appendChild(d); msgs().scrollTop=msgs().scrollHeight; };
    document.getElementById('send').onclick = async () => {
      const val = document.getElementById('inp').value.trim(); if(!val) return; addMsg('user', val); document.getElementById('inp').value='';
      const res = await fetch(API_BASE + '/chat/message', { method:'POST', headers:{ 'Content-Type':'application/json','X-API-Key':API_KEY }, body: JSON.stringify({conversation_id:conversationId, message:val, locale: navigator.language}) });
      const data = await res.json(); if(data.conversation_id && data.conversation_id!==conversationId){ conversationId = data.conversation_id; localStorage.setItem('cb_conversation_id', conversationId); }
      (data.messages||[]).forEach(m=> m.type==='text' && addMsg('assistant', m.content));
      (data.products||[]).forEach(p=> { const c=document.createElement('div'); c.style='border:1px solid #eee;padding:8px;border-radius:8px;margin:6px 0;display:flex;gap:8px;align-items:center;font-size:13px;'; c.innerHTML=`<img src="${p.image_url}" style="width:48px;height:48px;object-fit:cover;border-radius:6px"/>\
        <div style="flex:1">${p.name}<div style="color:#888">￥${(p.price||{}).value||''}</div></div>\
        <button style="background:#10b981;color:#fff;border:0;border-radius:6px;padding:6px 10px;cursor:pointer">加入</button>`; const btn=c.querySelector('button'); btn.onclick=async()=>{ await fetch(API_BASE+'/cart/items',{method:'POST',headers:{'Content-Type':'application/json','X-API-Key':API_KEY},body:JSON.stringify({conversation_id:conversationId,product_id:p.id,quantity:1})}); }; msgs().appendChild(c); msgs().scrollTop=msgs().scrollHeight; });
    };
  })();
}</script>
```

## 开发路线图（建议）
1) 打通最小链路：`/v1/chat/message` 规则匹配 + 返回商品卡片；`/v1/cart/items` 写库。
2) 加入限流与鉴权（API Key 校验 + Redis 限流）。
3) 完善规则模型（优先级/本地化/同义词），补充检索兜底。
4) 上线监控与日志，准备后台配置界面。
5) 迭代推荐策略与多路召回。

