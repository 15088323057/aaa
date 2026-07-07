import os
import secrets
from functools import wraps
from datetime import datetime, timedelta

from flask import Flask, render_template, request, redirect, session, abort
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# 使用环境变量或随机生成安全密钥
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))

# 登录失败记录，用于简单速率限制
LOGIN_ATTEMPTS = {}

# ─── 用户数据库（密码已使用 scrypt 哈希） ───────────────────────────────
USERS = {
    "admin": {
        "username": "admin",
        "password": generate_password_hash("admin123"),
        "role": "admin",
        "email": "admin@example.com",
        "phone": "13800138000",
        "balance": 99999
    },
    "alice": {
        "username": "alice",
        "password": generate_password_hash("alice2025"),
        "role": "user",
        "email": "alice@example.com",
        "phone": "13900139001",
        "balance": 100
    }
}


def get_user_info(username):
    """返回不包含密码字段的用户信息"""
    if username in USERS:
        info = USERS[username].copy()
        info.pop("password", None)
        return info
    return None


def check_login_rate_limit(ip):
    """简单的登录频率限制：同一 IP 5 分钟内失败超过 5 次则临时封禁"""
    now = datetime.now()
    if ip in LOGIN_ATTEMPTS:
        # 清理过期记录
        LOGIN_ATTEMPTS[ip] = [
            t for t in LOGIN_ATTEMPTS[ip] if now - t < timedelta(minutes=5)
        ]
        if len(LOGIN_ATTEMPTS[ip]) >= 5:
            return False
    return True


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

        # 验证用户名和密码（使用安全哈希比对）
        user = USERS.get(username)
        if user and check_password_hash(user["password"], password):
            # 登录成功：清除该 IP 的失败记录
            LOGIN_ATTEMPTS.pop(client_ip, None)
            session["username"] = username
            # 重新生成 session ID 防止 session 固定攻击
            session.regenerate()
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


if __name__ == "__main__":
    # 生产环境不要开启 debug 模式
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug_mode, host="0.0.0.0", port=5000)
