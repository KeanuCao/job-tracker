# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

求职 Tracker：Python3 + Flask + SQLite 的单体 Web 应用，前后端不分离（服务端 Jinja 渲染）。
仓库中没有测试、没有 lint 配置、没有 CI，验收方式是人工照着 `README.md` 一步步点。

## 常用命令

```bash
bash start.sh                 # 一键：建 .venv → 装依赖 → 启动（默认 0.0.0.0:5000）
PORT=8080 bash start.sh       # 换端口
HOST=127.0.0.1 bash start.sh  # 只监听本机

# 手动等价流程
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

- 唯一的依赖是 Flask（`requirements.txt`）。
- 没有测试框架，也不要新增测试：用户明确要求一次性交付、不写任何测试代码。
- 清空数据：删除 `job_tracker.db` 后重启即可（该文件已被 `.gitignore` 忽略）。

## 架构

`main.py` 是唯一的 Python 文件，同时承担入口、建表、路由三层职责；模板与静态资源在 `templates/`、`static/`。

**常量即配置（`main.py` 顶部）**
- `STATUSES`：有序的 8 个状态（顺序就是招聘流程：打招呼 → 发简历 → 电话沟通 → 一面 → 二面 → 三面 → Offer → 终止），`DEFAULT_STATUS = "打招呼"`，`PER_PAGE = 10`。
- 状态集合是唯一事实来源，`main.py` 用它做白名单校验，模板用同一个 `statuses` 变量渲染下拉框 —— 增删状态只改 `STATUSES` 一处。

**数据库**
- `DB_PATH` 固定在 `main.py` 同目录下的 `job_tracker.db`。
- `get_db()` 把连接缓存在 Flask 的 `g` 上，`teardown_appcontext` 负责关闭。
- `init_db()` 在**模块导入时**执行（幂等的 `CREATE TABLE IF NOT EXISTS`），所以 `python main.py` 和 `flask run` 都会自动建库建表，无需任何初始化步骤。
- 两张表：`jobs`（start_date / company / position / status / created_at / updated_at）与 `job_status_history`（job_id / status / changed_at）。

**状态流转是核心不变量**
- 修改状态 = 更新 `jobs.status` + `updated_at`，**并且**向 `job_status_history` 追加一行带时间戳的记录。
- 创建岗位时也会写一条 history（初始状态），所以详情页里最早的一条就是"创建时的状态"，状态相同时不写重复记录。
- 详情页的历史按 `changed_at DESC, id DESC` 展示，最新的在最上面。
- 删除岗位时会显式删除它的 history 行（不依赖外键级联，尽管建表带了 `ON DELETE CASCADE`）。

**路由**
`GET /`（创建表单 + 分页列表）、`POST /jobs/create`、`GET /jobs/<id>`（详情）、`POST /jobs/<id>/status`、`POST /jobs/<id>/delete`。
所有写操作都是 POST 后 redirect（PRG），用户提示走 `flash`，分类有 `ok` / `warn` / `error`，由 `base.html` 统一渲染。

**两个容易踩的排序/回跳细节**
- 列表排序是 `start_date DESC, id DESC`。创建后用同一排序算出新记录落在第几页（`create_job` 里的 `ahead` 计数查询）并 redirect 过去，保证"创建完一定能看到这条记录"。
- 列表里改状态时通过隐藏字段 `back` 带回当前页 URL，改完状态不会掉回第一页。新增类似的行内操作时请沿用这个模式。

**界面约定**：中文文案，面向老年用户 —— 基础字号 20px、按钮最小高度 46–52px、高对比配色，样式集中在 `static/style.css`。页面只有首页 `index.html` 和详情页 `detail.html`，布局与 flash 在 `base.html`。

## 其他约定

- 代码注释、提交信息、界面文案都用中文。
- 没有数据库迁移工具：改表结构需要自行处理已存在的 `job_tracker.db`（或让用户删除该文件重新开始）。
- `README.md` 是人工验收脚本，改功能时同步更新它。

---

## 原始需求（用户提供，原文保留）

以下内容来自本项目最初的交付要求，后续修改不得违背：

> 这是一个非常简单的项目，我要求你一次性的完成，尽可能快的完成。
> 不允许进行任何测试，单元测试，路径测试，各种测试的代码都不允许运行，只能一次性完成。否则我将会重置你所有的工作。非常非常很简单 rm -rf .。
> 不允许和我交互，我除了这个文档之外不会给你提供任何建议。
> 我将会按照readme中的向导一步一步验收。
>
> 项目要求
> 1. 这个是一个求职的tracker。用python3实现，不需要前后端分离。flask或者flaskapi可以使用，其他的你酌情。
> 2. 界面不用花哨，功能完备既可以。
> 3. 数据库用sqllite，放在main.py或者其他你设计的入口下面
> 4. 我可以录入一个job，job包含以下必要信息
>  - 开始日期
>  - 公司名称
>  - 职位名称
>  - Job状态，默认为打招呼。状态有（打招呼，发简历，电话沟通，一面，二面，三面，Offer，终止）
> 5. 一个页面就够了，一个创建按钮，一个Job列表。列表要求分页，对老年人友好。
> 6. Job可以删除。
> 7. 列表中可以直接修改Job的状态，每次修改状态需要记录时间。Job应该有详情，可以看到状态的流转。
>
> 人工验收:
> 1. 环境为一个干净的wsl环境，Python版本为3.12.x
> 2. Readme是必须的
> 3. 你完成后的代码会被提交到git。
> 4. wsl上将会checkout你的代码，并按照readme安装必须的依赖。
> 5. 最后用你提供的shell启动app
