#!/usr/bin/env python3
"""初始化用户数据库（首次运行前执行一次）"""

import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), "users.db")


def init_database():
    # 如果数据库已存在，先删除（方便重新初始化）
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 创建用户表
    cursor.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            email TEXT,
            phone TEXT,
            balance REAL DEFAULT 0.0
        )
    """)

    # 插入预置用户（密码自动哈希）
    users = [
        ("admin", "admin123", "admin", "admin@example.com", "13800138000", 99999),
        ("alice", "alice2025", "user", "alice@example.com", "13900139001", 100),
    ]

    for username, password, role, email, phone, balance in users:
        hashed_pw = generate_password_hash(password)
        cursor.execute(
            "INSERT INTO users (username, password, role, email, phone, balance) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (username, hashed_pw, role, email, phone, balance),
        )
        print(f"  ✅ 用户 {username} 创建成功")

    conn.commit()
    conn.close()
    print(f"\n📦 数据库已创建：{DB_PATH}")


if __name__ == "__main__":
    print("🔧 正在初始化用户数据库...\n")
    init_database()
    print("\n✨ 初始化完成！现在可以启动 Flask 服务了：")
    print("   python3 app.py")
