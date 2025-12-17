# Java｜双重检查单例竞态

## Details

### 漏洞成因
双重检查单例（Double-Checked Locking, DCL）常被用于懒加载单例实例：先在同步块外判断实例是否为空，进入同步块后再判断一次并创建对象。然而，如果实例字段未声明为 `volatile`，JVM 可能对写操作进行指令重排，导致其他线程在对象尚未完全构造时读到非空引用，出现 `NullPointerException`、配置缺失等问题。在旧版本 JDK（≤1.4）或 Android ART 上尤为常见，即便在现代 JDK 中，缺少 `volatile` 仍会埋下竞态隐患。

### 代码示例

**易受攻击示例：**
```java
public class LazySingleton {
    private static LazySingleton instance;              // 未使用 volatile

    public static LazySingleton getInstance() {
        if (instance == null) {                         // 外层检查
            synchronized (LazySingleton.class) {
                if (instance == null) {                 // 内层检查
                    instance = new LazySingleton();     // 可能被重排
                }
            }
        }
        return instance;                                // 其他线程读到半初始化对象
    }
}
```

**安全示例：**
```java
public class LazySingleton {
    private static volatile LazySingleton instance;

    public static LazySingleton getInstance() {
        if (instance == null) {
            synchronized (LazySingleton.class) {
                if (instance == null) {
                    instance = new LazySingleton();
                }
            }
        }
        return instance;
    }
}

// 更推荐的写法：
public enum EnumSingleton {
    INSTANCE;
}

// 或使用 Holder 模式
public class HolderSingleton {
    private static class Holder {
        private static final HolderSingleton INSTANCE = new HolderSingleton();
    }
    public static HolderSingleton getInstance() {
        return Holder.INSTANCE;
    }
}
```

### 快速定位技巧

#### 核心操作定位（审计等级：L1-L2）
**关键词扫描：** `double-checked`, `instance == null`, `lazy`, `singleton`, `volatile`。

**定位步骤：**
1. 全局搜索涉及懒加载单例的代码；
2. 跳读（L2）判断实例字段是否使用 `volatile` 或 `AtomicReference`；
3. 检查同步块是否锁在类对象或其他全局锁上。

#### 保护机制定位（审计等级：L2-L3）
**检查是否存在：**
- `volatile` 声明的实例字段；
- 采用 `enum` 单例、Holder 模式、`@Bean`/容器管理的单例；
- 使用 `AtomicReference`、`Lazy<T>` 等并发安全封装；
- 保证单例初始化在容器启动阶段完成。

**定位技巧：**
- 逐行读（L3）确认构造函数是否复杂（访问数据库、加载配置、抛异常）；
- 检查是否有多个入口创建实例，或子类覆盖影响线程安全；
- 跨模块追踪（L4）确保所有调用方都使用统一的获取方法。

#### 审计等级标注
| 场景 | 审计等级 | 说明 |
|------|----------|------|
| 使用 `enum`、Holder、容器管理单例 | **L0（快速跳过）** | 线程安全有保障 |
| 使用 `volatile` + 双检锁 | **L2（跳读）** | 快速确认是否覆盖所有场景 |
| 未使用 `volatile` 的双检锁 | **L3（逐行读）** | 高风险，需要深入审计 |
| 多模块复制懒加载逻辑 | **L4（跨模块追踪）** | 需全链路检查 |

## Classify

### 研判标准

#### 确认漏洞
1. 双检锁实现中 `instance` 未使用 `volatile` 或没有内存屏障；
2. 构造逻辑复杂，可能在发布前暴露未初始化状态；
3. 运行或压测中可复现异常（空指针、配置缺失）。

#### 误报
1. 单例使用 `enum`、Holder 模式或容器管理（Spring 单例 Bean）；
2. 懒加载发生在单线程启动阶段，后续不再并发访问；
3. 单例对象设计为只读常量，构造期间无外部可见状态。

#### 代码异味
1. 同时存在 `volatile` 与手动内存屏障，意图不明；
2. 依赖运行环境“恰好安全”而无注释说明；
3. 预留了 `TODO` 或注释计划迁移但迟迟未执行。

## Low risk

### 低风险评级场景

#### 1. 单例仅封装不可变配置
- 场景：对象构造后不再修改，偶发竞态只造成一次性读取失败；
- 评估：可暂列低风险，但建议改造。

#### 2. 初始化仅在启动阶段完成
- 场景：应用启动时由主线程调用并完成初始化，之后只读；
- 评估：风险较低，但需记录运行条件。

#### 3. 已有明确重构计划
- 场景：团队计划近期迁移到 `enum` 或 Holder 模式，并有跟踪工单；
- 评估：短期可降级，但必须跟进执行。

#### 风险降级条件总结
| 条件 | 降级理由 | 建议优先级 |
|------|----------|------------|
| 单例只读 | 影响范围小 | 中 |
| 启动阶段完成构造 | 运行期无竞态 | 中 |
| 重构计划明确 | 可暂时容忍 | 低 |

