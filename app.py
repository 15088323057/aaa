import os
import secrets
import sqlite3
import re
from functools import wraps
from datetime import datetime, timedelta

from flask import Flask, render_template, request, redirect, session, abort, send_file, flash, url_for, make_response
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# 最大上传文件大小限制：16MB
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

# 使用环境变量或随机生成安全密钥
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))

# 登录失败记录，用于简单速率限制
LOGIN_ATTEMPTS = {}

# 数据库路径（在 data/ 目录下）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DB_DIR, "users.db")


# ─── 数据库初始化 ───────────────────────────────────────────────

def init_db():
    """初始化数据库：创建目录、建表、插入默认用户"""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 建表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT,
            phone TEXT
        )
    """)

    # 插入默认用户（INSERT OR IGNORE 防止重复插入）
    default_users = [
        ("admin", generate_password_hash("admin123"), "admin@example.com", "13800138000"),
        ("alice", generate_password_hash("alice2025"), "alice@example.com", "13900139001"),
    ]
    for username, pw, email, phone in default_users:
        cursor.execute(
            "INSERT OR IGNORE INTO users (username, password, email, phone) VALUES (?, ?, ?, ?)",
            (username, pw, email, phone),
        )

    conn.commit()
    conn.close()
    print(f"📦 数据库已就绪：{DB_PATH}", flush=True)


# ─── 数据库操作函数 ───────────────────────────────────────────────

def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_user_by_username(username):
    """根据用户名查询用户（参数化查询 — 安全）"""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        if row:
            return dict(row)
        return None
    finally:
        conn.close()


def get_user_info(username):
    """返回不包含密码字段的用户信息"""
    user = get_user_by_username(username)
    if user:
        user.pop("password", None)
        user.pop("id", None)
        return user
    return None


def check_login_rate_limit(ip):
    """简单的登录频率限制：同一 IP 5 分钟内失败超过 5 次则临时封禁"""
    now = datetime.now()
    if ip in LOGIN_ATTEMPTS:
        LOGIN_ATTEMPTS[ip] = [
            t for t in LOGIN_ATTEMPTS[ip] if now - t < timedelta(minutes=5)
        ]
        if len(LOGIN_ATTEMPTS[ip]) >= 5:
            return False
    return True


# ─── 首页路由 ─────────────────────────────────────────────────

@app.route("/")
def index():
    username = session.get("username")
    user_info = get_user_info(username)
    return render_template("index.html", user=user_info, search_results=None, keyword="")


# ─── 登录（保持不变） ──────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        client_ip = request.remote_addr or "unknown"

        if not check_login_rate_limit(client_ip):
            return render_template(
                "login.html",
                error="登录失败次数过多，请 5 分钟后再试"
            )

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = get_user_by_username(username)

        if user and check_password_hash(user["password"], password):
            LOGIN_ATTEMPTS.pop(client_ip, None)
            session.clear()
            session["username"] = username
            user_info = get_user_info(username)
            return render_template("index.html", user=user_info, search_results=None, keyword="")
        else:
            LOGIN_ATTEMPTS.setdefault(client_ip, []).append(datetime.now())
            return render_template("login.html", error="用户名或密码错误")

    return render_template("login.html")


# ─── 注册（已修复 — 使用参数化查询） ────────────────────────────

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()

        if not username or not password:
            return render_template("register.html", error="用户名和密码不能为空")

        # 密码先哈希
        hashed_pw = generate_password_hash(password)

        # ✅ 已修复：使用参数化查询，防止 SQL 注入
        sql = "INSERT OR IGNORE INTO users (username, password, email, phone) VALUES (?, ?, ?, ?)"
        print(f"📝 [注册SQL] {sql} | 参数: username={username}", flush=True)

        conn = get_db()
        try:
            conn.execute(sql, (username, hashed_pw, email, phone))
            conn.commit()

            # 检查是否真的插入了
            check = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
            if check:
                return redirect("/login?msg=注册成功，请登录")
            else:
                return render_template("register.html", error="用户名已存在")
        except Exception as e:
            print(f"❌ 注册失败: {e}")
            return render_template("register.html", error="注册失败，请检查输入")
        finally:
            conn.close()

    # 读取 URL 中的提示消息
    msg = request.args.get("msg", "")
    return render_template("register.html", msg=msg)


# ─── 搜索（已修复 — 使用参数化查询） ────────────────────────────

@app.route("/search")
def search():
    keyword = request.args.get("keyword", "").strip()
    username = session.get("username")
    user_info = get_user_info(username)

    if not keyword:
        return render_template("index.html", user=user_info, search_results=None, keyword="")

    # ✅ 已修复：使用参数化查询，防止 SQL 注入
    sql = "SELECT id, username, email, phone FROM users WHERE username LIKE ? OR email LIKE ?"
    like_pattern = f"%{keyword}%"
    print(f"🔍 [搜索SQL] {sql} | 参数: '%{keyword}%'", flush=True)

    conn = get_db()
    try:
        rows = conn.execute(sql, (like_pattern, like_pattern)).fetchall()
        results = [dict(row) for row in rows]
        print(f"    → 找到 {len(results)} 条结果", flush=True)
        return render_template("index.html", user=user_info, search_results=results, keyword=keyword)
    except Exception as e:
        print(f"❌ 搜索出错: {e}", flush=True)
        return render_template("index.html", user=user_info, search_results=[], keyword=keyword, search_error="SQL 执行出错")
    finally:
        conn.close()


# ─── 登出 ───────────────────────────────────────────────────────


def safe_filename(filename):
    """过滤路径遍历字符，防止攻击者通过文件名逃逸到其他目录"""
    # 移除路径分隔符和转义字符
    filename = filename.replace("..", "").replace("/", "").replace("\\", "")
    # 只保留安全的 ASCII 字符
    filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    # 限制文件名长度
    if len(filename) > 200:
        name, ext = os.path.splitext(filename)
        filename = name[:190] + ext
    return filename or "uploaded_file"

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ─── 头像上传 ───────────────────────────────────────────────────

@app.route("/upload", methods=["GET", "POST"])
def upload_avatar():
    username = session.get("username")
    if not username:
        return redirect("/login")

    if request.method == "POST":
        file = request.files.get("file")
        if not file or file.filename == "":
            return render_template("upload.html", error="请选择要上传的文件")

        upload_dir = os.path.join(app.static_folder, "uploads")
        os.makedirs(upload_dir, exist_ok=True)

        # 安全过滤文件名，防止路径遍历
        raw_filename = file.filename
        if not raw_filename:
            return render_template("upload.html", error="无效的文件名")
        safe_name = safe_filename(raw_filename)

        # 避免同名文件覆盖：加入用户名和随机数前缀
        rand_suffix = secrets.token_hex(4)
        final_name = f"{session['username']}_{rand_suffix}_{safe_name}"
        filepath = os.path.join(upload_dir, final_name)
        file.save(filepath)

        file_url = url_for("static", filename=f"uploads/{final_name}")
        return render_template("upload.html", success=True, file_url=file_url)

    return render_template("upload.html")


# ─── 报告下载 ───────────────────────────────────────────────────

@app.route("/report")
def download_report():
    report_path = os.path.join(BASE_DIR, "安全漏洞审计报告.docx")
    return send_file(report_path, as_attachment=True, download_name="安全漏洞审计报告.docx")


# ─── 启动 ───────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug_mode, host="0.0.0.0", port=5000)
