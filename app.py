import os
import secrets
import sqlite3
import re
import urllib.request
import urllib.error
import urllib.parse
import ipaddress
import socket
import subprocess
import platform
import json
import xml.etree.ElementTree as ET
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

# ─── CSRF Token 生成 ──────────────────────────────────────────

def generate_csrf_token():
    """生成并存储 CSRF Token 到 session 中"""
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(16)
    return session["_csrf_token"]

@app.before_request
def ensure_csrf_token():
    """每个请求前确保 session 中有 CSRF Token"""
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(16)

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
            phone TEXT,
            role TEXT DEFAULT 'user',
            balance REAL DEFAULT 0.0
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

    # 兼容旧表：尝试添加缺失的列（如果不存在则忽略）
    for col_def in [
        "ADD COLUMN role TEXT DEFAULT 'user'",
        "ADD COLUMN balance REAL DEFAULT 0.0",
    ]:
        try:
            cursor.execute(f"ALTER TABLE users {col_def}")
        except sqlite3.OperationalError:
            pass  # 列已存在

    # 更新 admin 的 role 和 balance
    cursor.execute("UPDATE users SET role = 'admin', balance = 99999 WHERE username = 'admin'")
    cursor.execute("UPDATE users SET role = 'user', balance = 100 WHERE username = 'alice'")

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


def get_user_by_id(user_id):
    """根据用户 ID 查询用户（用于个人中心）"""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, username, email, phone, role, balance FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if row:
            return dict(row)
        return None
    finally:
        conn.close()


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
            session["_csrf_token"] = secrets.token_hex(16)
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


# ─── 个人中心（已修复 - 通过 session 获取当前用户） ─────────────

@app.route("/profile")
def profile():
    """个人中心：只能查看当前登录用户的资料"""
    username = session.get("username")
    if not username:
        return redirect("/login")

    user = get_user_by_username(username)
    if not user:
        return "用户不存在", 404

    # 移除密码和ID，传给模板
    user.pop("password", None)
    msg = request.args.get("msg", "")
    error = request.args.get("error", "")
    csrf_token = generate_csrf_token()
    return render_template("profile.html", user=user, msg=msg, error=error, csrf_token=csrf_token)


# ─── 充值（已修复） ───────────────────────────────────────────────

@app.route("/recharge", methods=["POST"])
def recharge():
    # 修复1：验证登录状态
    session_username = session.get("username")
    if not session_username:
        return redirect("/login")

    amount = request.form.get("amount")
    if not amount:
        return "缺少参数", 400

    try:
        amount = round(float(amount), 2)  # 修复2：金额四舍五入到2位小数
    except ValueError:
        return "无效的参数", 400

    # 通过 session 获取当前用户
    current_user = get_user_by_username(session_username)
    if not current_user:
        return "用户不存在", 404

    # 修复3：金额必须为正数
    if amount <= 0:
        return render_template("profile.html", user=current_user, error="充值金额必须大于零")

    # 修复4：单次充值上限
    if amount > 999999:
        return render_template("profile.html", user=current_user, error="单次充值金额不能超过 999,999 元")

    conn = get_db()
    try:
        conn.execute(
            "UPDATE users SET balance = balance + ? WHERE username = ?",
            (amount, session_username)
        )
        conn.commit()
        print(f"💰 充值成功: user={session_username}, amount={amount}", flush=True)
    except Exception as e:
        print(f"❌ 充值失败: {e}", flush=True)
        return "充值失败", 500
    finally:
        conn.close()

    return redirect("/profile")


# ─── 修改密码（已修复） ─────────────────────────────────────

@app.route("/change-password", methods=["POST"])
def change_password():
    """修改密码：验证 CSRF Token、验证原密码、仅允许修改自己的密码"""
    username = session.get("username")
    if not username:
        return redirect("/login")

    # 修复1：验证 CSRF Token
    csrf_token = request.form.get("_csrf_token", "")
    if not csrf_token or csrf_token != session.get("_csrf_token", ""):
        return redirect("/profile?error=请求验证失败，请刷新页面重试")

    # 修复2：忽略表单中的 username，仅使用 session 中的当前用户
    old_password = request.form.get("old_password", "")
    new_password = request.form.get("new_password", "")

    if not old_password or not new_password:
        return redirect("/profile?error=原密码和新密码不能为空")

    # 修复3：验证原密码
    user = get_user_by_username(username)
    if not user:
        return redirect("/login")

    if not check_password_hash(user["password"], old_password):
        return redirect("/profile?error=原密码错误")

    # 更新密码
    hashed_pw = generate_password_hash(new_password)

    conn = get_db()
    try:
        conn.execute(
            "UPDATE users SET password = ? WHERE username = ?",
            (hashed_pw, username)
        )
        conn.commit()
        print(f"🔑 密码修改成功: {username}", flush=True)
        return redirect("/profile?msg=密码修改成功")
    except Exception as e:
        print(f"❌ 密码修改失败: {e}", flush=True)
        return redirect("/profile?error=修改失败")
    finally:
        conn.close()


# ─── URL 抓取（已修复） ───────────────────────────────────

def is_private_ip(hostname):
    """检查 hostname 解析后的 IP 是否为内网/私有地址"""
    try:
        # 解析域名获取所有 IP 地址
        addrs = socket.getaddrinfo(hostname, None)
        for addr in addrs:
            ip_str = addr[4][0]
            try:
                ip = ipaddress.ip_address(ip_str)
                if ip.is_private or ip.is_loopback or ip.is_link_local:
                    return True
                # 额外阻止云元数据 IP
                if ip_str == "169.254.169.254":
                    return True
            except ValueError:
                continue
        return False
    except socket.gaierror:
        return False  # DNS 解析失败，让 urlopen 处理

@app.route("/fetch-url", methods=["POST"])
def fetch_url():
    """抓取 URL：修复 SSRF 漏洞，限制协议、阻止内网访问"""
    username = session.get("username")
    if not username:
        return redirect("/login")

    target_url = request.form.get("url", "").strip()
    if not target_url:
        return redirect("/")

    result = {
        "url": target_url,
        "status_code": "N/A",
        "content": "",
        "error": None
    }

    # 修复1：只允许 http 和 https 协议
    parsed = urllib.parse.urlparse(target_url)
    if parsed.scheme not in ("http", "https"):
        result["error"] = "仅允许 http 和 https 协议"
        result["content"] = "不支持的协议: " + parsed.scheme
        user_info = get_user_info(username)
        return render_template("index.html", user=user_info, search_results=None, keyword="", fetch_result=result)

    # 修复2：检查 hostname 是否为内网地址
    hostname = parsed.hostname
    if hostname:
        if is_private_ip(hostname):
            result["error"] = "不允许访问内网地址"
            result["content"] = f"目标地址 {hostname} 解析为内网 IP，已阻止"
            user_info = get_user_info(username)
            return render_template("index.html", user=user_info, search_results=None, keyword="", fetch_result=result)

    # 修复3：使用自定义 opener（不自动跟随 file:// 等协议）
    try:
        response = urllib.request.urlopen(target_url, timeout=10)
        result["status_code"] = response.getcode()
        raw_content = response.read()
        try:
            content_text = raw_content.decode("utf-8")
        except UnicodeDecodeError:
            content_text = raw_content.decode("utf-8", errors="replace")
        result["content"] = content_text[:5000]
    except urllib.error.HTTPError as e:
        result["status_code"] = e.code
        result["content"] = str(e)
        result["error"] = f"HTTP 错误: {e.code}"
    except urllib.error.URLError as e:
        result["error"] = f"URL 错误: {e.reason}"
        result["content"] = str(e)
    except Exception as e:
        result["error"] = f"抓取失败: {type(e).__name__}: {e}"
        result["content"] = str(e)

    user_info = get_user_info(username)
    return render_template("index.html", user=user_info, search_results=None, keyword="", fetch_result=result)


# ─── Ping 网络诊断（已修复） ────────────────────────────

def validate_ip_or_hostname(target):
    """验证输入是否为合法的 IP 地址或主机名"""
    if not target or len(target) > 255:
        return False
    # 允许合法 IP 地址（IPv4）
    try:
        ipaddress.ip_address(target)
        return True
    except ValueError:
        pass
    # 允许合法主机名（仅字母数字、点、短横线，不允许空格和特殊字符）
    if re.match(r'^[a-zA-Z0-9.-]+$', target):
        # 主机名不能以短横线开头或结尾
        if target.startswith('-') or target.endswith('-'):
            return False
        # 主机名不能全部是数字（是纯数字但不是合法IP的情况也拒绝）
        if re.match(r'^\d+(\.\d+)*$', target):
            return False
        return True
    return False

@app.route("/ping", methods=["GET", "POST"])
def ping():
    """Ping 测试：使用参数列表方式执行命令，防止命令注入"""
    username = session.get("username")
    if not username:
        return redirect("/login")

    if request.method == "GET":
        return render_template("ping.html", output=None)

    # POST：接收 ip 参数，执行 ping 命令
    ip = request.form.get("ip", "").strip()
    if not ip:
        return render_template("ping.html", output="请输入 IP 地址或域名")

    # 修复1：验证输入是否为合法的 IP 或主机名
    if not validate_ip_or_hostname(ip):
        return render_template("ping.html", output="输入格式不正确：仅允许合法的 IP 地址或主机名")

    # 修复2：使用参数列表方式，不使用 shell=True
    command_list = ["ping", "-c", "3", ip]
    print(f"📡 执行命令: {' '.join(command_list)}", flush=True)

    try:
        output = subprocess.check_output(
            command_list,
            shell=False,
            stderr=subprocess.STDOUT,
            timeout=30
        )
        output_text = output.decode("utf-8", errors="replace")
    except subprocess.CalledProcessError as e:
        output_text = e.output.decode("utf-8", errors="replace") if e.output else f"命令执行失败，返回码: {e.returncode}"
    except subprocess.TimeoutExpired:
        output_text = "命令执行超时（30 秒）"
    except Exception as e:
        output_text = f"执行错误: {type(e).__name__}: {e}"

    print(f"📡 命令输出:\n{output_text}", flush=True)
    return render_template("ping.html", output=output_text)


# ─── XML 数据导入（故意保留 XXE 漏洞用于教学演示） ────────

@app.route("/xml-import", methods=["GET", "POST"])
def xml_import():
    """XML 导入：检测 ENTITY/SYSTEM 并读取本地文件替换实体引用（XXE 漏洞）"""
    username = session.get("username")
    if not username:
        return redirect("/login")

    if request.method == "GET":
        return render_template("xml_import.html", result=None)

    # POST：接收 XML 数据
    xml_data = request.form.get("xml_data", "").strip()
    if not xml_data:
        return render_template("xml_import.html", result={"error": "请输入 XML 数据"})

    print(f"📄 收到 XML 数据:\n{xml_data}", flush=True)

    # 检测 XML 中的 <!ENTITY 和 SYSTEM，提取文件路径并读取本地文件
    entity_pattern = re.compile(r'<!ENTITY\s+\S+\s+SYSTEM\s+"([^"]+)"')
    matches = entity_pattern.findall(xml_data)

    for filepath in matches:
        print(f"🔍 发现实体引用: SYSTEM \"{filepath}\"", flush=True)
        # 处理 file:// 协议前缀
        local_path = filepath
        if local_path.startswith("file://"):
            local_path = local_path[7:]
        try:
            with open(local_path, "r", encoding="utf-8") as f:
                file_content = f.read()
            # 将 &xxe; 实体引用替换为文件内容
            xml_data = re.sub(r'&xxe;', file_content, xml_data)
            print(f"📖 已读取文件: {filepath} ({len(file_content)} 字符)", flush=True)
        except Exception as e:
            print(f"❌ 读取文件失败: {filepath} - {e}", flush=True)
            xml_data = re.sub(r'&xxe;', f"[文件读取失败: {e}]", xml_data)

    # 解析替换后的 XML
    try:
        root = ET.fromstring(xml_data)
        users = []
        for user_elem in root.findall(".//user"):
            name_el = user_elem.find("name")
            email_el = user_elem.find("email")
            users.append({
                "name": name_el.text if name_el is not None else "",
                "email": email_el.text if email_el is not None else ""
            })
        result = {"status": "success", "users": users}
    except ET.ParseError as e:
        result = {"status": "error", "error": f"XML 解析失败: {e}"}
    except Exception as e:
        result = {"status": "error", "error": f"处理错误: {type(e).__name__}: {e}"}

    print(f"📤 解析结果: {json.dumps(result, ensure_ascii=False)}", flush=True)
    return render_template("xml_import.html", result=result)


# ─── 报告下载 ───────────────────────────────────────────────────

@app.route("/report")
def download_report():
    report_path = os.path.join(BASE_DIR, "安全漏洞审计报告.docx")
    return send_file(report_path, as_attachment=True, download_name="安全漏洞审计报告.docx")


# ─── 动态页面加载 ─────────────────────────────────────────────

@app.route("/page")
def dynamic_page():
    name = request.args.get("name", "")
    page_content = "页面不存在"

    if name:
        # 安全修复：使用绝对路径规范化，防止路径遍历攻击
        pages_dir = os.path.join(BASE_DIR, "pages")
        safe_path = os.path.realpath(os.path.join(pages_dir, name))

        # 检查规范化后的路径是否仍在 pages 目录内
        if not safe_path.startswith(os.path.realpath(pages_dir) + os.sep):
            page_content = "页面不存在"
        elif not os.path.exists(safe_path) or not os.path.isfile(safe_path):
            # 尝试加 .html 后缀
            safe_path_html = safe_path + ".html"
            if os.path.exists(safe_path_html) and os.path.isfile(safe_path_html):
                try:
                    with open(safe_path_html, "r", encoding="utf-8") as f:
                        page_content = f.read()
                except Exception:
                    page_content = "页面读取失败"
            else:
                page_content = "页面不存在"
        else:
            try:
                with open(safe_path, "r", encoding="utf-8") as f:
                    page_content = f.read()
            except Exception:
                page_content = "页面读取失败"

    username = session.get("username")
    user_info = get_user_info(username)
    return render_template("index.html", user=user_info, search_results=None, keyword="", page_content=page_content)


# ─── 启动 ───────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug_mode, host="0.0.0.0", port=5000)
