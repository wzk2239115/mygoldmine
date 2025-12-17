---
name: race-conditions-analyzer
description: 专业的审计工作流程，通过静态与动态分析识别并验证竞态条件与数据竞争；重点关注多线程、多进程或异步执行中共享状态的访问顺序、锁粒度及原子性缺失，并结合各语言参考指南定位高危并发缺陷。
---

**Attention**  
当代码出现“多线程/多进程/异步协程共享可变状态”且缺乏恰当的同步（互斥锁、原子操作、事务隔离、幂等控制）时，极易演化为竞态条件，导致数据覆盖、权限绕过、重复执行、资源争用等问题。常见于任务调度、计费/支付、库存扣减、消息消费、缓存失效更新、临时文件写入等高并发场景，需要重点审计共享状态读写顺序与临界区保护。

**Early exit**  
若项目为严格顺序执行（单线程脚本）、或仅包含不可变数据处理、或所有共享状态均托管给具备事务保证的外部服务（且无本地缓存/重入逻辑）、或模块已全面使用可靠的并发抽象（不可变结构、STM、原子事务）且无自定义同步逻辑，则可快速结束该漏洞类型的审计。
---

## 通用竞态条件漏洞模式（所有项目必审）

查看详细说明：[general.md](general.md)

快速概览：共享状态访问无同步、TOCTOU 竞态、数据库事务隔离缺失、缓存更新竞态、文件系统竞态、原子性不足、幂等性缺失、分布式环境竞态、业务逻辑竞态

---

**语言特定实现（根据项目语言选择性审计）**

以下漏洞场景与具体编程语言的并发机制实现方式相关。根据项目所使用的编程语言，仅需审计对应语言章节中的漏洞模式。

**Java**  
常见于使用 `synchronized`/`volatile` 不当、使用非线程安全集合、或双重检查锁定实现错误；在分布式环境中，重复请求幂等控制缺失也会触发竞态。  
- 非线程安全集合（如 `HashMap`）在多线程写场景下使用，详见：[java_non_threadsafe_collection.md](java_non_threadsafe_collection.md)  
- 双重检查单例中内存可见性问题，详见：[java_double_checked_singleton.md](java_double_checked_singleton.md)  
- Spring 事务外部的缓存更新窗口，详见：[java_cache_invalidation_race.md](java_cache_invalidation_race.md)

**Python**  
常见于多线程（尤其 CPython GIL 释放场景）、多进程、异步协程共享全局状态时缺乏锁；文件/数据库写入缺少幂等控制易导致重复执行。  
- `threading` 多线程访问共享字典未加锁，详见：[python_threading_shared_dict_race.md](python_threading_shared_dict_race.md)  
- `asyncio` 并发任务更新同一缓存键缺少锁，详见：[python_asyncio_cache_window.md](python_asyncio_cache_window.md)  
- 多进程写同一临时文件未使用 `fcntl`/`flock`，详见：[python_file_lock_race.md](python_file_lock_race.md)

**Go**  
常见于 goroutine 并发访问 map、切片或全局结构体未加锁，或通过 channel 进行信号同步时存在未受控分支；HTTP Handler/定时任务重复执行时缺乏原子校验。  
- 多 goroutine 写共享 map 触发 `fatal error: concurrent map writes`，详见：[go_concurrent_map_write.md](go_concurrent_map_write.md)  
- 使用 `sync.Once`/`sync.Mutex` 不当导致初始化竞态，详见：[go_once_initialization_race.md](go_once_initialization_race.md)  
- 定时任务与即时请求同时修改库存，详见：[go_inventory_update_race.md](go_inventory_update_race.md)

**PHP**  
常见于依赖文件锁或数据库更新的 Web 场景：同一资源请求并发到达时，缺少锁或事务隔离导致重复扣费/订单状态异常；CLI worker 与 Web 进程同时更新同一行数据也易出现竞态。  
- `file_put_contents` 写缓存文件未加锁导致内容交错，详见：[php_file_write_race.md](php_file_write_race.md)  
- 使用 `UPDATE` 减库存但缺少行锁/版本号控制，详见：[php_inventory_update_race.md](php_inventory_update_race.md)  
- Session/Token 刷新接口未设置原子校验，详见：[php_token_refresh_race.md](php_token_refresh_race.md)  
- 文件上传竞态条件漏洞，详见：[php_upload_race_condition.md](php_upload_race_condition.md)

**JavaScript (Node.js)**  
常见于多实例部署、Cluster/Fork、Worker Threads、共享缓存层等场景；异步 Promise 并发更新同一资源或依赖非原子文件操作也会触发竞态。  
- Node.js Cluster 进程共享临时文件未加锁，详见：[js_cluster_tempfile_race.md](js_cluster_tempfile_race.md)  
- Promise 并发刷新缓存导致脏数据覆盖，详见：[js_promise_cache_race.md](js_promise_cache_race.md)  
- 使用 `fs.writeFile` 竞争导致部分写入，详见：[js_fs_write_race.md](js_fs_write_race.md)

**TypeScript**  
常见于 NestJS/Express 等后端服务使用 async/await 并发访问共享内存、全局 Map、LRU 缓存或第三方 SDK，无锁或无原子 CAS；在 Serverless 环境中跨请求复用全局变量也会引发竞态。  
- TypeScript 服务端共享 Map 更新缺乏互斥控制，详见：[ts_shared_map_mutex.md](ts_shared_map_mutex.md)  
- TypeORM 乐观锁未启用导致并发覆盖，详见：[ts_typeorm_optimistic_lock_missing.md](ts_typeorm_optimistic_lock_missing.md)  
- Serverless 冷启动后的全局缓存竞态，详见：[ts_serverless_global_state_race.md](ts_serverless_global_state_race.md)

**C/C++**  
常见于使用 POSIX 线程、std::thread、信号处理或异步回调时对共享内存、全局变量、文件句柄未加锁或锁粒度过细，亦或忘记使用 `volatile`/内存屏障致使编译器重排。  
- 多线程写共享缓冲区但缺少互斥保护，详见：[c_shared_buffer_data_race.md](c_shared_buffer_data_race.md)  
- 双重检查锁定实现不当导致竞争窗口，详见：[cpp_double_checked_locking.md](cpp_double_checked_locking.md)  
- 信号处理与主线程共享状态未使用原子操作，详见：[c_signal_handler_race.md](c_signal_handler_race.md)

**Rust**  
常见于错误使用 `Arc<Mutex>`/`RwLock`、滥用 `unsafe`、或在异步代码中跨任务共享可变状态；通过 `RefCell`/`Cell` 绕过借用检查也可能埋下竞态隐患。  
- `Arc<Mutex>` 解锁顺序不当导致死锁与竞态窗口，详见：[rust_mutex_lock_ordering.md](rust_mutex_lock_ordering.md)  
- `Send`/`Sync` 自定义实现缺陷导致数据竞争，详见：[rust_manual_send_sync_race.md](rust_manual_send_sync_race.md)  
- Tokio 异步任务共享 `Rc<RefCell>` 造成竞态访问，详见：[rust_tokio_refcell_race.md](rust_tokio_refcell_race.md)

## 快速开始

### 步骤 0：理解项目功能与结构

**在开始审计之前，彻底理解项目的功能与结构，特别关注并发处理相关的实现：**

- 查阅项目文档，重点关注多线程/多进程/异步处理机制说明
- 理解业务领域和核心功能，识别涉及并发访问的场景（支付、库存、计费、任务调度等）
- 识别关键组件、模块及其关系，特别是高并发模块、队列消费者、缓存层、定时任务
- 梳理应用流程（重点：并发请求处理流程、异步任务调度机制、缓存更新策略）
- 识别关键业务功能（库存扣减、订单创建、支付处理、积分充值、消息消费、文件写入等）
- 理解所用技术栈和框架（并发库、线程池、异步框架、ORM 事务机制、缓存中间件、消息队列等）
- 查阅配置文件以理解系统行为（线程池大小、事务隔离级别、重试策略、锁超时配置等）
- 定位共享状态的访问位置（全局变量、静态字段、缓存、数据库记录、文件系统等）
- 定位并发控制机制（互斥锁、读写锁、原子操作、数据库事务、分布式锁、版本号/乐观锁等）
- 识别并发入口（HTTP 接口、消息队列消费者、定时任务、异步回调、WebSocket 连接等）

**Early exit（早期退出）：**

在理解项目结构的过程中，如果发现项目不符合前面 **Early exit** 章节描述的条件（例如严格单线程执行、无共享可变状态、所有并发已托管给具备完整事务保证的外部服务等），可立即退出该漏洞类型的审计，无需继续深入分析。

只有在确认项目存在并发处理机制和共享状态访问，并获得足够的项目背景信息后，才继续查阅各漏洞类型的参考指南并开始有针对性的漏洞分析。

### 步骤 1：查阅竞态条件漏洞的参考指南

竞态条件漏洞审计分为两个层次，需要按顺序进行：

**第一步：审计通用竞态条件漏洞模式（所有项目必审）**

在 **通用竞态条件漏洞模式** 章节中，列举了所有涉及并发处理的应用都必须审计的安全问题：
- 共享状态访问缺乏同步机制（多线程/进程访问、异步并发、锁使用不当），遇到锁保护机制详见：[bypassTricks.md#锁竞争和临界区](bypassTricks.md#锁竞争和临界区)
- 检查时间与使用时间差异 (TOCTOU)（先检查后使用、双重检查锁定），遇到时间窗口保护详见：[bypassTricks.md#检查-使用toctou竞争](bypassTricks.md#检查-使用toctou竞争)
- 数据库操作缺乏事务隔离（读后更新非原子、无行锁/乐观锁、批量操作），遇到事务保护详见：[bypassTricks.md#数据库事务的竞争](bypassTricks.md#数据库事务的竞争)
- 缓存更新竞态（缓存与数据库不一致、缓存击穿/雪崩），遇到缓存保护详见：[bypassTricks.md#缓存失效竞争](bypassTricks.md#缓存失效竞争)
- 文件系统操作竞态（文件读写无锁、文件路径 TOCTOU），遇到文件锁保护详见：[bypassTricks.md#文件系统竞争](bypassTricks.md#文件系统竞争)
- 原子性操作不足（非原子复合操作、计数器竞态），遇到原子性保护详见：[bypassTricks.md#状态同步竞争](bypassTricks.md#状态同步竞争)
- 幂等性控制缺失（重复请求未校验、状态机转换），遇到令牌保护详见：[bypassTricks.md#令牌和验证码重用](bypassTricks.md#令牌和验证码重用)
- 分布式环境竞态条件（多实例无分布式锁、分布式事务、消息队列），遇到异步处理保护详见：[bypassTricks.md#利用异步处理的竞争](bypassTricks.md#利用异步处理的竞争)
- 业务逻辑竞态（库存扣减、优惠券领取、余额充值扣减），遇到业务校验详见：[bypassTricks.md#金额和库存竞争](bypassTricks.md#金额和库存竞争)

这些问题与编程语言无关，是并发控制设计层面的通用缺陷，任何并发应用都需要检查。

**第二步：审计语言特定实现（根据项目语言选择性审计）**

在 **语言特定实现** 章节中，按编程语言组织了各语言并发机制实现方式的特定问题：
- 按编程语言分类（Java、Python、Go、PHP、JavaScript、TypeScript、C/C++、Rust）
- 列出该语言并发原语和框架的典型竞态缺陷和对应的参考文档链接

根据项目所用编程语言，仅需查找和审计对应语言章节中的漏洞场景。

### 步骤 2：深入学习具体的审计指南

根据 **通用竞态条件漏洞模式** 和 **语言特定实现** 章节中的引用，打开对应的具体审计指南文件（如 `race_shared_state_no_lock.md`、`java_non_threadsafe_collection.md`、`go_concurrent_map_write.md` 等）。这些文件主要包含三个核心部分：

1. **Details（详细说明）**：漏洞成因、危险代码与安全代码对比示例、快速定位技巧（核心操作定位和保护机制定位）
2. **Classify（分类研判）**：明确的研判标准，包括确认漏洞、判定误报、识别代码异味的具体条件
3. **Low risk（低风险场景）**：列举可以降低风险等级的场景和条件

通过学习这些具体指南，可以准确识别代码中的竞态条件模式，并进行有效的审计和评估。

## 核心审计原则

### 验证要求

- 必须根据实际源代码验证发现结果，而非仅依赖模式匹配
- 必须验证完整的竞态条件触发链：并发入口 → 共享状态访问 → 同步机制缺失/不当 → 竞态窗口 → 安全影响
- 每一步都需要文件路径、函数名和行号的具体证据
- 考虑框架和项目中实现的自动防护（事务隔离、乐观锁、原子操作等）
- 遇到任何保护机制需要绕过时，参考详细利用技巧：[bypassTricks.md](bypassTricks.md)

# 输出要求

确认漏洞后，加载 `bug-report` 技能获取标准化报告格式，生成漏洞报告文件。

**加载技能**：`bug-report`

**输出路径**：`.workspace/findings/BUG-race-conditions-{file}-L{line}-{source}-{sink}.md`

**约束**：
- 每个漏洞必须生成独立的 BUG 文件，禁止合并或省略
- 漏洞报告格式严格遵循 `bug-report` 技能定义的模板
