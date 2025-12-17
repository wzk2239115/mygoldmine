# C/C++ Boost.Serialization 类型混淆

## Details

### 典型代码示例

```cpp
// 场景1: 多态基类反序列化，类型ID未验证
class Base {
public:
    virtual ~Base() {}
    template<class Archive> void serialize(Archive& ar, const unsigned int) {}
};
class DerivedA : public Base {
    int value;
    template<class Archive> void serialize(Archive& ar, const unsigned int) {
        ar & value;
    }
};
class DerivedB : public Base {
    char* ptr;  // 危险：指针字段
    template<class Archive> void serialize(Archive& ar, const unsigned int) {
        ar & ptr;
    }
};
void load_object(std::istream& is) {
    boost::archive::binary_iarchive ia(is);
    Base* obj;
    ia >> obj;  // 类型ID从流中读取，可被伪造
}

// 场景2: 使用 BOOST_CLASS_EXPORT 但无类型白名单
BOOST_CLASS_EXPORT(DerivedA)
BOOST_CLASS_EXPORT(DerivedB)
void deserialize_config(const char* data, size_t len) {
    std::stringstream ss(std::string(data, len));
    boost::archive::text_iarchive ia(ss);
    Base* cfg;
    ia >> cfg;  // 可反序列化为任意已注册类型
}

// 场景3: 直接反序列化到基类指针，后续类型转换
void process_message(std::istream& stream) {
    boost::archive::xml_iarchive ia(stream);
    Base* msg;
    ia >> msg;
    DerivedA* da = dynamic_cast<DerivedA*>(msg);  // 类型混淆后转换失败或错误
    da->value = 100;  // 可能访问错误的内存布局
}

// 场景4: 模板特化反序列化，类型参数可控
template<typename T>
void load_typed_data(std::istream& is) {
    boost::archive::binary_iarchive ia(is);
    T obj;
    ia >> obj;  // T 从外部输入决定，可指定为危险类型
}
```

### 快速定位核心操作 (审计技巧)

**L1 (关键词扫描)**  
- 搜索：`boost::archive`, `boost::serialization`, `BOOST_CLASS_EXPORT`, `BOOST_SERIALIZATION_ASSUME_ABSTRACT`
- 反序列化入口：`ia >>`, `ia.load()`, `boost::archive::*_iarchive`, `text_iarchive`, `binary_iarchive`, `xml_iarchive`
- 多态相关：`Base*`, `virtual`, `dynamic_cast` 配合反序列化

**L2 (跳读)**  
- 定位数据源：`std::istream` 参数来源（网络流、文件、内存缓冲区）
- 检查类型注册：查找 `BOOST_CLASS_EXPORT` 宏，确认哪些类型可被反序列化
- 关注指针反序列化：`ia >> ptr` 直接反序列化指针，而非值类型

**L3 (逐行读)**  
- 验证类型检查：反序列化后是否有 `dynamic_cast` 或 `typeid` 验证
- 检查类型白名单：是否存在自定义 `archive` 或 `binder` 限制可反序列化类型
- 多态基类布局：基类是否包含虚函数表，派生类布局差异

**L4 (跨模块追踪)**  
- 追踪类型注册链：`BOOST_CLASS_EXPORT` 在哪些编译单元中注册，是否包含危险类型
- 检查工厂模式：反序列化后对象是否通过工厂创建，工厂是否有类型限制
- 分析继承层次：多态继承树中哪些类型可被混淆，内存布局差异

### 快速定位保护机制 (审计技巧)

**L0 (快速跳过)**  
- 仅值类型序列化：反序列化为具体类型（非基类指针），且无多态
- 类型硬编码：模板参数为编译期常量，无法从外部控制

**L1 (关键词扫描)**  
- 类型检查关键词：`dynamic_cast`, `typeid`, `instanceof`, `Binder`, `type_info`
- 白名单机制：`allowed_types`, `type_whitelist`, `register_type` 配合验证

**L2 (跳读)**  
- 检查类型验证：反序列化后立即进行 `dynamic_cast` 或类型比较
- 自定义 Archive：继承 `boost::archive::*_iarchive` 并重写类型解析逻辑
- 版本/魔数校验：序列化数据头部包含版本号或魔数，类型ID在验证后使用

**L3 (逐行读)**  
- 类型白名单实现：`Binder` 或自定义 `load_override` 中检查类型ID是否在允许列表
- 内存布局验证：反序列化后检查对象虚函数表指针是否合法
- 类型一致性：序列化时的类型ID与反序列化时期望的类型ID是否匹配

**L4 (跨模块追踪)**  
- 全局类型注册审计：所有 `BOOST_CLASS_EXPORT` 调用点，确认无危险类型泄露
- 序列化协议版本：检查是否有版本升级机制，旧版本类型ID是否被禁用
- 沙箱隔离：反序列化是否在受限环境中执行，类型混淆影响范围

## Classify

### 确认为漏洞的条件
1. **多态基类指针反序列化无验证**：从流中读取类型ID后直接构造对象，未检查类型ID是否在允许范围内
2. **类型注册过度开放**：`BOOST_CLASS_EXPORT` 注册了包含指针、回调函数或危险虚函数的类型，且无白名单限制
3. **类型混淆导致内存布局错误**：通过伪造类型ID，将 `DerivedA`（小对象）反序列化为 `DerivedB`（大对象含指针），后续访问越界
4. **模板类型参数可控**：反序列化的模板类型 `T` 可从外部输入决定，允许指定任意已注册类型
5. **虚函数表劫持**：类型混淆后，对象虚函数表指针指向错误类型，虚函数调用触发代码执行

### 判定为误报的情况
1. **数据源完全可信**：序列化数据来自同一进程的序列化操作，且中间无外部修改（如进程内缓存）
2. **类型硬编码且已验证**：反序列化目标类型在编译期确定，且序列化数据来源已验证完整性（签名、哈希）
3. **仅值类型无多态**：反序列化为具体结构体/类（非基类指针），无虚函数，类型混淆无影响
4. **严格类型白名单**：实现了自定义 `Archive` 或 `Binder`，仅允许白名单内的类型ID，且实现无绕过可能
5. **类型ID校验完整**：反序列化后立即进行 `dynamic_cast` 验证，类型不匹配则拒绝，且验证逻辑无缺陷

### 代码异味（需进一步确认）
1. **部分类型注册**：部分派生类使用了 `BOOST_CLASS_EXPORT`，但基类反序列化时可能匹配到未注册类型
2. **类型检查延迟**：反序列化后未立即验证类型，中间有其他操作可能依赖错误类型假设
3. **继承层次复杂**：多继承或深继承层次，类型ID映射可能产生歧义
4. **序列化版本不一致**：不同版本代码注册的类型ID不同，但反序列化时未检查版本兼容性
5. **类型注册位置分散**：`BOOST_CLASS_EXPORT` 在多个编译单元中注册，难以审计完整类型集合

## Low risk

### 低风险评级场景

1. **类型混淆影响受限**  
   - 混淆后的类型内存布局相似，无指针字段差异，仅标量值错误
   - 混淆类型均为只读查询类，无虚函数调用或危险操作
   - 类型混淆后对象立即被验证并丢弃，无后续使用

2. **数据源受限**  
   - 序列化数据来自本地可信文件（非网络、非共享存储）
   - 仅在调试/开发模式下启用的反序列化路径
   - 需要特定权限（如 root）才能触发的配置加载

3. **类型注册严格**  
   - 所有已注册类型均为 POD 类型或简单值类型，无指针、无虚函数
   - 类型注册数量极少（< 5 个），且均为业务逻辑安全类型
   - 类型ID与业务逻辑强绑定，伪造类型ID会导致业务逻辑立即失败

4. **纵深防御到位**  
   - 进程运行在严格沙箱中，类型混淆无法导致代码执行
   - 启用 CFI（控制流完整性），虚函数表劫持被阻止
   - 反序列化后的对象仅用于统计/日志，不影响程序控制流

5. **快速失效机制**  
   - 类型混淆后首次虚函数调用立即触发断言或段错误
   - 对象使用前有完整性校验（魔数、校验和），异常类型无法通过
   - 类型验证失败后进程立即终止，无持续利用可能

6. **已有补偿控制**  
   - 业务层对反序列化结果进行二次类型验证和业务逻辑校验
   - 监控系统能检测异常类型ID的出现并告警
   - 类型混淆影响范围仅限于单个请求，无持久化状态污染
