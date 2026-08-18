

https://github.com/user-attachments/assets/108c7a0b-51bc-46e7-83e2-a8bc98080495

# 企业级 RAG 个人知识问答系统

基于检索增强生成 (RAG) 技术的企业级知识问答平台，支持多格式文档上传、智能分块、混合检索、流式问答和引用溯源。

## 功能特性

- 多格式文档支持：PDF、Word、Markdown、HTML、TXT
- 智能分块：按 Token 预算语义分块，带重叠窗口
- 混合检索：向量检索 (Dense) + BM25 关键词检索 (Sparse) + RRF 融合
- 重排序：支持 BGE-Reranker Cross-Encoder 精排
- 流式问答：SSE 流式输出，实时显示生成内容
- 引用溯源：每条回答附带引用来源，可查看原文
- 多轮对话：支持上下文追问，对话历史管理
- 用户认证：JWT 认证 + RBAC 权限控制
- 响应式 UI：React + TypeScript + Tailwind CSS

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | FastAPI + Python 3.12 |
| 前端 | React 18 + TypeScript + Vite + Tailwind |
| 向量库 | NumPy 内存向量库 (开发) / Milvus (生产) |
| 数据库 | SQLite (开发) / PostgreSQL (生产) |
| Embedding | OpenAI 兼容 API / BGE-M3 本地模型 |
| LLM | OpenAI 兼容 API (OpenAI/DeepSeek/Ollama/vLLM) |
| 部署 | Docker + Nginx |

## 快速开始

### 方式一：Docker Compose 一键部署

```bash
# 1. 复制环境配置
cp .env.example .env

# 2. 编辑 .env，填入你的 LLM API Key
#    至少需要配置 LLM_API_KEY 和 EMBEDDING_API_KEY

# 3. 启动所有服务
docker-compose up -d --build

# 4. 访问
#    前端: http://localhost
#    API 文档: http://localhost:8000/docs
```

### 方式二：本地开发

#### 后端

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp ../.env.example ../.env
# 编辑 ../.env 填入 API Key

# 启动后端
python main.py
# 或: uvicorn main:app --reload --port 8000
```

#### 前端

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
# 访问 http://localhost:5173
```

## 配置说明

编辑 `.env` 文件配置以下关键参数：

### LLM 配置
支持任何 OpenAI 兼容 API：

```bash
# OpenAI
LLM_API_BASE=https://api.openai.com/v1
LLM_API_KEY=sk-xxx
LLM_MODEL=gpt-4o-mini

# DeepSeek
LLM_API_BASE=https://api.deepseek.com/v1
LLM_API_KEY=sk-xxx
LLM_MODEL=deepseek-chat

# Ollama (本地)
LLM_API_BASE=http://localhost:11434/v1
LLM_API_KEY=ollama
LLM_MODEL=qwen2.5:7b
```

### Embedding 配置
```bash
# OpenAI
EMBEDDING_API_BASE=https://api.openai.com/v1
EMBEDDING_API_KEY=sk-xxx
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIM=1536

# Ollama (本地)
EMBEDDING_API_BASE=http://localhost:11434/v1
EMBEDDING_API_KEY=ollama
EMBEDDING_MODEL=bge-m3
EMBEDDING_DIM=1024
```

### 检索配置
```bash
RETRIEVAL_TOP_K=50        # 初始检索数量
RERANK_TOP_K=10           # 重排后返回数量
VECTOR_SEARCH_WEIGHT=0.6  # 向量检索权重
BM25_SEARCH_WEIGHT=0.4    # BM25 检索权重
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/auth/register | 用户注册 |
| POST | /api/v1/auth/login | 用户登录 |
| GET | /api/v1/auth/me | 获取当前用户 |
| POST | /api/v1/documents/upload | 上传文档 |
| GET | /api/v1/documents | 文档列表 |
| DELETE | /api/v1/documents/{id} | 删除文档 |
| GET | /api/v1/stats | 知识库统计 |
| POST | /api/v1/chat | 知识问答 (SSE 流式) |
| GET | /api/v1/conversations | 对话列表 |
| GET | /api/v1/conversations/{id} | 对话详情 |
| DELETE | /api/v1/conversations/{id} | 删除对话 |

完整 API 文档: http://localhost:8000/docs

## 项目结构

```
RAG/
+-- docker-compose.yml          # Docker 编排
+-- .env.example                # 环境变量模板
+-- nginx/
|   +-- nginx.conf              # 反向代理配置
+-- backend/
|   +-- Dockerfile
|   +-- requirements.txt
|   +-- main.py                 # FastAPI 入口
|   +-- app/
|       +-- config.py           # 配置管理
|       +-- database.py         # 数据库连接
|       +-- models/             # SQLAlchemy 模型
|       +-- schemas/            # Pydantic 模型
|       +-- api/                # API 路由
|       +-- services/           # 业务逻辑
|       +-- core/               # 认证与依赖
+-- frontend/
    +-- Dockerfile
    +-- package.json
    +-- src/
        +-- api/                # API 调用
        +-- components/         # React 组件
        +-- contexts/           # Context Provider
        +-- pages/             # 页面
        +-- types/             # TypeScript 类型
```

## 架构设计

系统采用六层架构：
1. 数据接入层：多格式文档解析与采集
2. 文档处理层：智能分块、向量化、元数据提取
3. 存储层：NumPy 向量库 + SQLite/PostgreSQL + 文件存储
4. 检索层：混合检索 (Vector + BM25) + RRF 融合 + Reranker
5. 生成层：LLM 流式推理 + Prompt 工程 + 引用溯源
6. 应用层：FastAPI API + React UI + JWT 认证

## License

MIT
