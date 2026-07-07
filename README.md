# 用户信息管理平台

一个基于 Python Flask 的简易用户信息管理平台，用于演示 Web 安全漏洞及修复。

## 功能

- ✅ 用户登录（含频率限制，防暴力破解）
- ✅ 用户信息展示（用户名、邮箱、手机、角色、余额）
- ✅ 密码安全存储（scrypt 哈希）
- ✅ 安全漏洞审计报告下载

## 快速开始

### 1. 安装依赖

```bash
pip install flask werkzeug
```

### 2. 初始化数据库

```bash
python3 db_init.py
```

执行后会在当前目录生成 `users.db` 文件，包含以下预置用户：

| 用户名 | 密码 | 角色 | 邮箱 | 手机 | 余额 |
|--------|------|------|------|------|------|
| admin | admin123 | admin | admin@example.com | 13800138000 | 99999 |
| alice | alice2025 | user | alice@example.com | 13900139001 | 100 |

### 3. 启动服务

```bash
python3 app.py
```

访问 http://127.0.0.1:5000

### 4. 下载安全报告

启动服务后访问：http://127.0.0.1:5000/report

## 项目结构

```
.
├── app.py              # Flask 主应用（路由 + 数据库操作）
├── db_init.py          # 数据库初始化脚本（首次运行前执行）
├── users.db            # SQLite 用户数据库（自动生成，不提交到 Git）
├── generate_report.py  # Word 漏洞报告生成脚本
├── 安全漏洞审计报告.docx # 安全审计报告
├── .gitignore
├── README.md
├── templates/
│   ├── base.html       # 基础模板（导航栏、布局）
│   ├── index.html      # 首页（用户信息展示）
│   └── login.html      # 登录页
└── static/
    └── css/
        └── style.css   # 样式文件
```

## 安全特性

- **密码哈希存储**：使用 werkzeug.security 的 scrypt 算法哈希存储，不可逆
- **密码安全比对**：使用 check_password_hash() 恒定时间比对，防时序攻击
- **密钥管理**：secret_key 从环境变量读取，默认随机生成
- **速率限制**：同一 IP 5 分钟内登录失败超过 5 次则临时封禁
- **Session 加固**：登录成功后清除旧 session，防固定攻击
- **数据代码分离**：用户数据存储在独立的 SQLite 数据库中，不写在代码里

## 数据库说明

用户数据存储在 `users.db`（SQLite）中，与代码分离。首次运行需执行：

```bash
python3 db_init.py
```

初始化后 `users.db` 包含 `users` 表，结构如下：

```sql
CREATE TABLE users (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,        -- scrypt 哈希值
    role     TEXT NOT NULL,
    email    TEXT,
    phone    TEXT,
    balance  REAL DEFAULT 0.0
);
```

> ⚠️ `users.db` 已在 `.gitignore` 中忽略，不会上传到 Git 仓库。

## 许可

MIT License
