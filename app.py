import os
import secrets
import sqlite3
from functools import wraps
from datetime import datetime, timedelta

from flask import Flask, render_template, request, redirect, session, abort, send_file
from werkzeug.security import check_password_hash

app = Flask(__name__)

# 使用环境变量或随机生成安全密钥
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))

# 登录失败记录，用于简单速率限制
LOGIN_ATTEMPTS = {}

# 数据库路径
DB_PATH = os.path.join(os.path.dirname(__file__), "users.db")


# ─── 数据库操作函数 ───────────────────────────────────────────────

def get_db():
    """获取数据库连接（每次请求独立连接，用完自动关闭）"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # 让查询结果支持用字段名访问
    return conn


def get_user_by_username(username):
    """根据用户名查询用户（包含密码字段）"""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        if row:
            return dict(row)  # sqlite3.Row → 普通字典
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


# ─── 路由 ─────────────────────────────────────────────────────

@app.route("/")
def index():
    username = session.get("username")
    user_info = get_user_info(username)
    return render_template("index.html", user=user_info)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        client_ip = request.remote_addr or "unknown"

        # 速率限制检查
        if not check_login_rate_limit(client_ip):
            return render_template(
                "login.html",
                error="登录失败次数过多，请 5 分钟后再试"
            )

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        # 从数据库查询用户（密码哈希存储在数据库中）
        user = get_user_by_username(username)

        if user and check_password_hash(user["password"], password):
            # 登录成功
            LOGIN_ATTEMPTS.pop(client_ip, None)
            session.clear()
            session["username"] = username
            user_info = get_user_info(username)
            return render_template("index.html", user=user_info)
        else:
            # 记录失败尝试
            LOGIN_ATTEMPTS.setdefault(client_ip, []).append(datetime.now())
            return render_template("login.html", error="用户名或密码错误")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/report")
def download_report():
    """下载安全漏洞审计报告"""
    report_path = os.path.join(os.path.dirname(__file__), "安全漏洞审计报告.docx")
    return send_file(report_path, as_attachment=True, download_name="安全漏洞审计报告.docx")


if __name__ == "__main__":
    # 检查数据库是否已初始化
    if not os.path.exists(DB_PATH):
        print("⚠️  数据库文件不存在！请先运行：")
        print("   python3 db_init.py")
        print("然后重新启动本应用。\n")
        exit(1)

    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug_mode, host="0.0.0.0", port=5000)
