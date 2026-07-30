# MySQL 入门指南 — 掌柜问数项目

> 面向零基础，结合掌柜问数项目的实际场景编写。配合你已有的操作经验阅读效果最佳。

---

## 一、MySQL 基本原理

### 1.1 什么是数据库？——用 Excel 类比

如果你用过 Excel，数据库就很好理解：

| Excel 概念 | MySQL 对应 | 说明 |
|-----------|-----------|------|
| 一个 `.xlsx` 文件 | **数据库（Database）** | 一个独立的存储空间 |
| 一个 Sheet 工作表 | **表（Table）** | 一张二维表格 |
| 表头（A 列、B 列...） | **列 / 字段（Column）** | 每一列的标题和类型 |
| 每一行数据 | **行 / 记录（Row）** | 一条具体的数据 |
| Excel 程序本身 | **MySQL 服务** | 负责管理、增删改查 |

Excel 适合一个人偶尔看看几百行数据；但当数据量上百万行、很多人同时读写时，就需要数据库来管理。

### 1.2 什么是"关系型"数据库？

MySQL 属于**关系型数据库（RDBMS）**——"关系型"三个字是理解 MySQL 的钥匙。

它的核心思想很简单：**数据不堆在一张表里，而是拆成多张表，表之间通过"关系"关联起来。**

为什么不能全放一张表？假设你把所有数据塞进一张大表：

```
订单ID | 客户名 | 性别 | 等级 | 商品名   | 单价 | 数量 | 地区
1001   | 李伟   | 男   | 黄金 | iPhone  | 6999 | 2    | 广东-华南
1002   | 李伟   | 男   | 黄金 | MacBook | 9999 | 1    | 广东-华南
1003   | 李伟   | 男   | 黄金 | iPad    | 3499 | 3    | 广东-华南
```

问题显而易见：李伟的信息（姓名、性别、等级）存了 3 遍，浪费空间；想改"黄金"→"铂金"要改 3 个地方，容易出错。

关系型数据库的解决办法：**拆表**。

```
dim_customer（客户表）               fact_order（订单表）
┌────────────┬──────┬──────┐        ┌──────┬────────────┬───────┐
│ customer_id│ name │ level│        │order │ customer_id│ amount│
├────────────┼──────┼──────┤        ├──────┼────────────┼───────┤
│ C001       │ 李伟 │ 黄金 │        │ 1001 │ C001       │ 13998 │
│ C002       │ 王芳 │ 白银 │        │ 1002 │ C001       │  9999 │
└────────────┴──────┴──────┘        │ 1003 │ C001       │ 10497 │
                                    └──────┴────────────┴───────┘
```

李伟的信息只存一次，两张表通过 `customer_id` 关联。这就是"关系"的含义——数据分散但互相关联。

### 1.3 表与表之间的三种关系

拆表之后，表之间的关系有三种类型。理解这三种关系，你就能看懂项目中所有 SQL 的设计。

#### 一对多（最常见）

**一个地区有多个客户，一个客户只属于一个地区。**

```
dim_region                          dim_customer
┌───────────┬──────────┐            ┌────────────┬──────┬───────────┐
│ region_id │ name     │            │ customer_id│ name │ region_id │
├───────────┼──────────┤            ├────────────┼──────┼───────────┤
│ R004      │ 华北     │◄───────────│ C001       │ 李伟 │ R004      │
│ R001      │ 华南     │◄──┐        │ C002       │ 王芳 │ R001      │
└───────────┴──────────┘   │        │ C003       │ 张敏 │ R001      │
                           └────────│ C004       │ 刘洋 │ R004      │
                                    └────────────┴──────┴───────────┘
```

这就是 `dim_region` 和 `dim_customer` 在本项目中的实际关系。

#### 多对多

**一个订单可以包含多个商品，一个商品也可以出现在多个订单中。**

```
fact_order                          order_detail（中间表）
┌──────┬────────────┐               ┌──────┬───────────┬──────┐
│ 1001 │ C001       │──────┐        │ 1001 │ P001      │ 2    │
│ 1002 │ C001       │      └───────►│ 1001 │ P002      │ 1    │
└──────┴────────────┘               │ 1002 │ P001      │ 1    │
                                    └──────┴───────────┴──────┘
dim_product                                           │
┌───────┬──────────┬──────┐                           │
│ P001  │ iPhone   │ 6999 │◄──────────────────────────┘
│ P002  │ MacBook  │ 9999 │
└───────┴──────────┴──────┘
```

需要一个中间表（`order_detail`）来记录"订单 1001 买了 2 台 iPhone 和 1 台 MacBook"。

#### 一对一（较少见）

**一个客户只有一个会员卡号，一个会员卡号只属于一个客户。**

```sql
CREATE TABLE vip_card (
    card_id   VARCHAR(20) PRIMARY KEY,
    customer_id VARCHAR(20) UNIQUE,  -- UNIQUE 确保一对一
    points    INT
);
```

---

### 1.4 主键（Primary Key）与外键（Foreign Key）

关系型数据库靠主键和外键来维护表之间的关系。

#### 主键 — 每行数据的"身份证号"

每张表都应该有一个主键，用来**唯一标识**每一行数据。

```sql
-- dim_region 表的主键是 region_id
CREATE TABLE dim_region (
    region_id   VARCHAR(20) PRIMARY KEY,  -- ← 主键：每个地区有唯一编号
    region_name VARCHAR(50)
);
```

主键的特性：永不重复、不能为空、一张表只能有一个。

#### 外键 — 表与表之间的"纽带"

外键是另一张表的主键，用来建立表之间的关联。

```sql
-- 客户表的 region_id 是地区表主键的"引用"
-- 查询时通过它把两张表关联起来
SELECT c.name, r.region_name
FROM dim_customer c
JOIN dim_region r ON c.region_id = r.region_id;  -- 外键 = 主键 → 建立关联
```

#### 本项目中的主外键实例

查看 `dw.sql` 中的表结构：

```
dim_region.region_id  → 主键
dim_customer.region_id → 外键（引用 dim_region.region_id）

meta 库中：
table_info.id        → 主键
column_info.table_id  → 外键（引用 table_info.id）
metric_info.table_id  → 外键（引用 table_info.id）
```

---

### 1.5 常用的数据类型

创建表时必须为每一列指定数据类型。以下是最常用的几种：

| 类型 | 用途 | 本项目实例 |
|------|------|-----------|
| `VARCHAR(N)` | 可变长度字符串，最多 N 个字符 | `name VARCHAR(128)` — 表名 |
| `INT` | 整数 | `age INT` — 年龄 |
| `TEXT` | 长文本，不限长度 | `description TEXT` — 字段描述 |
| `JSON` | 存储 JSON 格式数据 | `alias JSON` — 字段别名数组 |
| `DATE` / `DATETIME` | 日期 / 日期时间 | `order_date DATE` — 下单日期 |
| `DECIMAL(M,N)` | 精确小数，M 位总长，N 位小数 | `amount DECIMAL(12,2)` — 金额 |
| `BOOLEAN` / `TINYINT(1)` | 布尔值（真/假） | `is_dimension TINYINT(1)` — 是否为维度字段 |

类型选错会有什么后果？如果金额用 `VARCHAR` 存，`SUM()` 就会报错——数据库不知道 `"一百元"` 该怎么加。

---

### 1.6 SQL 语言的四种分类

SQL 语句按照功能分为四类（这个分类在 `meta.sql` 和 `dw.sql` 中都能找到对应）：

| 分类 | 全称 | 作用 | 关键字 | 本项目中出现位置 |
|------|------|------|--------|----------------|
| **DDL** | Data Definition Language | 定义数据库结构（建库、建表、改表） | `CREATE`, `DROP`, `ALTER` | `meta.sql` 第 2-48 行 |
| **DML** | Data Manipulation Language | 操作数据（增、删、改） | `INSERT`, `UPDATE`, `DELETE` | `dw.sql` 中的 `INSERT INTO` 语句 |
| **DQL** | Data Query Language | 查询数据 | `SELECT` | 几乎每段业务代码都用 |
| **DCL** | Data Control Language | 控制权限 | `GRANT`, `REVOKE` | `meta.sql` 第 3 行 `GRANT` |

帮你理解：DDL 是"盖房子"（建结构），DML 是"搬家具"（放数据），DQL 是"找东西"（查数据），DCL 是"配钥匙"（管权限）。

### 1.7 在掌柜问数项目里，MySQL 存什么？

项目中用到了 **两个数据库**，各司其职：

| 数据库名 | 作用 | 存什么 |
|---------|------|--------|
| `meta` | **元数据库** | 描述"数据仓库里有哪些表、有哪些字段、有哪些指标" |
| `dw` | **数据仓库** | 存储实际的业务数据，如订单、用户、地区 |

打个比方：`meta` 是图书馆的**目录卡片**，告诉你"3 楼 2 排有计算机类书籍"；`dw` 是**书架上的书本身**。

#### meta 库的 4 张表及其关系

```
table_info（表信息）          column_info（字段信息）
┌──────┬────────────┬──┐      ┌──────┬──────────┬──────────┐
│ id   │ name       │..│      │ id   │ name     │ table_id │
├──────┼────────────┼──┤      ├──────┼──────────┼──────────┤
│ T001 │ fact_order │  │◄─────│ C001 │ order_id │ T001     │
│ T002 │ dim_region │  │◄─────│ C002 │ region_id│ T002     │
└──────┴────────────┴──┘      └──────┴──────────┴──────────┘

metric_info（指标定义）       column_metric（字段-指标关联）
┌──────┬──────────┬──────────┐  ┌──────────┬──────────┐
│ id   │ name     │ table_id │  │ column_id│ metric_id│
├──────┼──────────┼──────────┤  ├──────────┼──────────┤
│ M001 │ 销售总额 │ T001     │  │ C004     │ M001     │
│ M002 │ 订单数量 │ T001     │  │ C004     │ M002     │
└──────┴──────────┴──────────┘  └──────────┴──────────┘
```

这张图解释了掌柜问数系统的核心思路：LLM 先从 `meta` 库找到"销售额"对应哪个字段（`table_info` + `column_info` + `metric_info`），再从 `dw` 库执行对应 SQL 提取数据。

> 元数据的作用将在第 1.8 节详细展开。

### 1.8 为什么需要元数据？

回想掌柜问数的场景：用户说"统计去年的销售总额"。系统怎么知道：

- "销售额"指的是 `dw` 库中哪个字段？
- 是 `order_amount` 还是 `total_price` 还是 `revenue`？
- 用 `SUM()` 还是 `AVG()`？
- 在 `fact_order` 表里还是 `order_summary` 表里？

这就是 `meta` 元数据库存在的意义——它不是业务数据，而是**描述业务数据的数据**。

```
用户问题："统计去年的销售总额"
         ↓
meta 库检索：
  metric_info → 找到"销售总额" = SUM(order_amount)
  column_info → 找到 order_amount 属于 fact_order 表
  column_value → 找到 order_date 字段可取 "去年" 的时间范围
         ↓
LLM 根据以上信息生成 SQL：
  SELECT SUM(order_amount) FROM fact_order
  WHERE order_date BETWEEN '2025-01-01' AND '2025-12-31'
         ↓
dw 库执行 SQL → 返回结果给用户
```

一句话：**没有 meta 库，LLM 就像蒙着眼睛猜 SQL；有了 meta 库，LLM 有了目录和地图。**

---

## 二、MySQL 基础使用

### 2.1 连接 MySQL

连接 MySQL 需要四样东西：

```
主机地址 : 端口 / 用户名 : 密码
localhost : 3306 / root   : kkxdw
```

- **主机地址（host）**：MySQL 装在哪台机器上。`localhost` 表示本机
- **端口（port）**：MySQL 监听的"门牌号"，默认 3306
- **用户名和密码**：登录凭证，不同用户有不同权限

### 2.2 常用的 SQL 语句

SQL 是操作数据库的"语言"。以下是最常用的几句：

```sql
-- 查看有哪些数据库
SHOW DATABASES;

-- 切换到某个数据库（相当于双击打开一个文件夹）
USE meta;

-- 查看当前数据库有哪些表
SHOW TABLES;

-- 查看表的结构（列名、类型等）
DESCRIBE table_info;

-- 查询数据（SELECT 是最常用的语句）
SELECT * FROM table_info;                    -- 查所有行所有列
SELECT name, description FROM table_info;     -- 只查指定列
SELECT * FROM table_info WHERE name = '销售额'; -- 加条件筛选

-- 创建数据库
CREATE DATABASE IF NOT EXISTS my_db;

-- 创建表
CREATE TABLE users (
    id   INT PRIMARY KEY,
    name VARCHAR(50),
    age  INT
);

-- 插入数据
INSERT INTO users (id, name, age) VALUES (1, '张三', 25);

-- 更新数据
UPDATE users SET age = 26 WHERE name = '张三';

-- 删除数据
DELETE FROM users WHERE id = 1;
```

### 2.3 用户与权限

MySQL 中不同用户可以有不同的权限：

```sql
-- 查看某个用户有哪些权限
SHOW GRANTS FOR 'kkx'@'%';

-- kkx@% 的含义：
--   kkx  = 用户名
--   %    = 可以从任意主机连接（localhost 或远程都行）
```

常见的权限级别：

| 权限范围 | 能做什么 |
|---------|---------|
| `USAGE` | 仅能登录，什么也干不了 |
| `SELECT ON db.*` | 只能查，不能改 |
| `ALL PRIVILEGES ON db.*` | 对该库有完全控制权 |

---

## 三、掌柜问数项目中的 MySQL 操作

### 3.1 项目架构中 MySQL 的位置

```
你的电脑
 └─ Docker Desktop（容器平台）
     ├─ MySQL 容器（端口 3306）
     │   ├─ meta 数据库 → 4 张表：table_info / column_info / metric_info / column_metric
     │   └─ dw   数据库 → 业务表：dim_region / dim_customer / fact_order 等
     ├─ Qdrant 容器（端口 6333）— 向量检索
     ├─ Elasticsearch 容器（端口 9200）— 全文检索
     ├─ Kibana 容器（端口 5601）— ES 管理界面
     └─ Embedding 容器（端口 8081）— 文本向量化
```

MySQL 通过 Docker 运行，好处是：不需要在 Windows 上手动安装，一条 `docker compose up -d` 就能启动。

### 3.2 启动 MySQL

```bash
cd D:\Desktop\Claude Code\data-agent\docker
docker compose up -d
```

`-d` 表示后台运行。启动后验证：

```bash
docker compose ps          # 看所有容器状态
docker exec mysql mysql -u root -pkkxdw -e "SELECT 1;"   # 验证 MySQL 可连接
```

### 3.3 导入数据

项目提供了两个初始化 SQL 文件：`docker/mysql/meta.sql` 和 `docker/mysql/dw.sql`。

**用 root 用户导入（推荐）**：

```bash
# 需要先进入 docker 目录
cd D:\Desktop\Claude Code\data-agent\docker

# Git Bash 环境
cat mysql/meta.sql | docker exec -i mysql mysql -u root -pkkxdw
cat mysql/dw.sql   | docker exec -i mysql mysql -u root -pkkxdw

# CMD 环境
type mysql\meta.sql | docker exec -i mysql mysql -u root -pkkxdw
type mysql\dw.sql   | docker exec -i mysql mysql -u root -pkkxdw
```

命令结构拆解：

```
type mysql\meta.sql          →  读取 SQL 文件内容
|                            →  （管道）把内容传给下一个命令
docker exec -i mysql         →  在 mysql 容器中执行命令，-i 表示接收输入
mysql -u root -pkkxdw         →  以 root 身份连接 MySQL
```

### 3.4 在命令行中操作 MySQL

```bash
# 进入交互模式（退出用 exit）
docker exec -it mysql mysql -u kkx -pkkxdw -D meta
# -it  = 交互模式
# -D meta = 直接进入 meta 数据库

# 在交互模式中：
mysql> SHOW TABLES;
mysql> SELECT * FROM table_info;
mysql> exit
```

### 3.5 在 PyCharm 中操作 MySQL

这是项目中日常使用最频繁的方式。

**Step 1：连接数据库**

PyCharm 右侧边栏 → `Database`（数据库）→ `+` → `Data Source` → `MySQL`

填写连接信息：

| 字段 | 值 |
|------|-----|
| Host | `localhost` |
| Port | `3306` |
| User | `kkx` |
| Password | `kkxdw` |
| Database | 先不填，连接后能看到所有库 |

点 `Test Connection` 测试，成功后点 `OK`。

**Step 2：查看数据**

连接成功后，PyCharm 的 Database 面板会显示 `meta` 和 `dw` 两个库。展开可以看到表，双击表名就能浏览数据。

**Step 3：写 SQL 查询**

右键某个数据库 → `New` → `Query Console`，打开查询控制台：

```sql
-- 看看有哪些元数据表
USE meta;
SELECT * FROM table_info;

-- 看看 dw 里有哪些地区
USE dw;
SELECT * FROM dim_region;

-- 统计每个地区的客户数
SELECT region_name, COUNT(*) AS customer_count
FROM dim_customer c
JOIN dim_region r ON c.region_id = r.region_id
GROUP BY region_name;
```

**Step 4：导入 SQL 文件**

PyCharm 中也可以直接导入 SQL 脚本：
右键数据库 → `Run SQL Script...` → 选择 `meta.sql` 或 `dw.sql` → 执行。

---

## 四、总结：你在项目中已经做过的事

回顾一下你实际操作过的步骤，这些就是 MySQL 最核心的使用流程：

```
1. 启动 Docker → MySQL 容器跑起来
2. 连接 MySQL → 用命令行或 PyCharm
3. 查看数据库 → SHOW DATABASES
4. 导入 SQL 脚本 → type ... | docker exec
5. 排错 → GRANT 权限问题、atguigu vs kkx 用户不匹配
6. 验证 → SHOW TABLES、SELECT *
```

掌握这些就足够支撑掌柜问数项目的开发了。如果需要深入了解 MySQL 的高级特性（索引、事务、性能优化等），随时可以继续。
