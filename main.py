#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""求职 Tracker —— 单文件 Flask 应用（前后端不分离）。

启动方式：
    python3 main.py
然后浏览器打开 http://127.0.0.1:5000

数据库为 SQLite，文件 job_tracker.db 与本文件放在同一目录下，
首次启动会自动创建表和数据库文件。
"""

import os
import sqlite3
from datetime import date, datetime

from flask import (Flask, flash, g, redirect, render_template, request,
                   url_for)

# --------------------------------------------------------------------------
# 基础配置
# --------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "job_tracker.db")

# Job 状态（按招聘流程的先后顺序排列）
STATUSES = ["打招呼", "发简历", "电话沟通", "一面", "二面", "三面", "Offer", "终止"]
DEFAULT_STATUS = "打招呼"

PER_PAGE = 10  # 列表每页条数
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "5000"))

app = Flask(__name__)
app.secret_key = "job-tracker-secret-key"


# --------------------------------------------------------------------------
# 数据库工具
# --------------------------------------------------------------------------
def get_db():
    """取得当前请求的数据库连接（不存在则新建）。"""
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_db():
    """初始化数据库表结构（幂等，可重复执行）。"""
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            start_date  TEXT NOT NULL,
            company     TEXT NOT NULL,
            position    TEXT NOT NULL,
            status      TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS job_status_history (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id     INTEGER NOT NULL,
            status     TEXT NOT NULL,
            changed_at TEXT NOT NULL,
            FOREIGN KEY (job_id) REFERENCES jobs (id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_jobs_start_date ON jobs (start_date DESC, id DESC);
        CREATE INDEX IF NOT EXISTS idx_history_job ON job_status_history (job_id);
        """
    )
    conn.commit()
    conn.close()


def get_job_or_none(job_id):
    row = get_db().execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return row


# --------------------------------------------------------------------------
# 路由
# --------------------------------------------------------------------------
@app.route("/")
def index():
    """首页：新增表单 + 岗位列表（分页）。"""
    try:
        page = int(request.args.get("page", 1))
    except (TypeError, ValueError):
        page = 1
    if page < 1:
        page = 1

    db = get_db()
    total = db.execute("SELECT COUNT(*) AS c FROM jobs").fetchone()["c"]
    total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    if page > total_pages:
        page = total_pages

    jobs = db.execute(
        """
        SELECT * FROM jobs
        ORDER BY start_date DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        (PER_PAGE, (page - 1) * PER_PAGE),
    ).fetchall()

    return render_template(
        "index.html",
        jobs=jobs,
        statuses=STATUSES,
        default_status=DEFAULT_STATUS,
        today=date.today().isoformat(),
        page=page,
        total=total,
        total_pages=total_pages,
        per_page=PER_PAGE,
    )


@app.route("/jobs/create", methods=["POST"])
def create_job():
    """新增一个岗位。"""
    start_date = (request.form.get("start_date") or "").strip()
    company = (request.form.get("company") or "").strip()
    position = (request.form.get("position") or "").strip()
    status = (request.form.get("status") or "").strip()

    if not start_date:
        start_date = date.today().isoformat()
    if status not in STATUSES:
        status = DEFAULT_STATUS

    if not company or not position:
        flash("公司名称和职位名称都不能为空。", "error")
        return redirect(url_for("index"))

    ts = now_str()
    db = get_db()
    cur = db.execute(
        """
        INSERT INTO jobs (start_date, company, position, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (start_date, company, position, status, ts, ts),
    )
    job_id = cur.lastrowid
    # 初始状态也记入流转历史
    db.execute(
        "INSERT INTO job_status_history (job_id, status, changed_at) VALUES (?, ?, ?)",
        (job_id, status, ts),
    )
    db.commit()

    # 列表按「开始日期倒序、id 倒序」排列，算出新记录落在第几页，
    # 直接跳过去，保证创建后一定能看到它。
    ahead = db.execute(
        """
        SELECT COUNT(*) AS c FROM jobs
        WHERE start_date > ? OR (start_date = ? AND id > ?)
        """,
        (start_date, start_date, job_id),
    ).fetchone()["c"]
    page = ahead // PER_PAGE + 1

    flash("岗位「%s - %s」创建成功。" % (company, position), "ok")
    return redirect(url_for("index", page=page))


@app.route("/jobs/<int:job_id>")
def job_detail(job_id):
    """岗位详情：基本信息 + 状态流转记录。"""
    db = get_db()
    job = get_job_or_none(job_id)
    if job is None:
        flash("岗位不存在或已被删除。", "error")
        return redirect(url_for("index"))

    history = db.execute(
        """
        SELECT * FROM job_status_history
        WHERE job_id = ?
        ORDER BY changed_at DESC, id DESC
        """,
        (job_id,),
    ).fetchall()

    return render_template("detail.html", job=job, history=history, statuses=STATUSES)


@app.route("/jobs/<int:job_id>/status", methods=["POST"])
def update_status(job_id):
    """在列表中直接修改岗位状态，并记录修改时间。"""
    job = get_job_or_none(job_id)
    if job is None:
        flash("岗位不存在或已被删除。", "error")
        return redirect(url_for("index"))

    new_status = (request.form.get("status") or "").strip()
    if new_status not in STATUSES:
        flash("无效的状态值。", "error")
        return redirect(url_for("index", page=request.args.get("page", 1)))

    back = request.form.get("back") or url_for("index")

    if new_status == job["status"]:
        flash("状态没有变化，仍是「%s」。" % new_status, "warn")
        return redirect(back)

    ts = now_str()
    db = get_db()
    db.execute(
        "UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?",
        (new_status, ts, job_id),
    )
    db.execute(
        "INSERT INTO job_status_history (job_id, status, changed_at) VALUES (?, ?, ?)",
        (job_id, new_status, ts),
    )
    db.commit()
    flash(
        "「%s - %s」状态已由「%s」改为「%s」。"
        % (job["company"], job["position"], job["status"], new_status),
        "ok",
    )
    return redirect(back)


@app.route("/jobs/<int:job_id>/delete", methods=["POST"])
def delete_job(job_id):
    """删除岗位（同时删除它的状态流转记录）。"""
    job = get_job_or_none(job_id)
    if job is None:
        flash("岗位不存在或已被删除。", "error")
        return redirect(url_for("index"))

    db = get_db()
    db.execute("DELETE FROM job_status_history WHERE job_id = ?", (job_id,))
    db.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    db.commit()
    flash("岗位「%s - %s」已删除。" % (job["company"], job["position"]), "ok")
    return redirect(url_for("index"))


# --------------------------------------------------------------------------
# 启动
# --------------------------------------------------------------------------
init_db()

if __name__ == "__main__":
    print("求职 Tracker 已启动： http://127.0.0.1:%d" % PORT)
    app.run(host=HOST, port=PORT, debug=False)
