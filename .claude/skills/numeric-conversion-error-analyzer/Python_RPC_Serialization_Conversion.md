# Python_RPC_Serialization_Conversion

**漏洞类型**: RPC 序列化转换错误，RPC 反序列化中的类型转换导致精度丢失、溢出、类型混淆

**漏洞成因**

Python RPC 序列化/反序列化中的类型转换存在以下风险：
- msgpack/pickle 反序列化大整数转浮点，导致精度丢失
- 协议缓冲区（protobuf）中大整数字段转换溢出
- thrift/RPC 消息中数值类型不匹配导致转换
- 有符号/无符号整数混淆，反序列化后值误解
- 浮点数序列化再反序列化，舍入误差累积
- 数组/列表元素的类型转换不一致
- RPC 服务端/客户端对数值类型的理解差异

---

## Details

### 代码示例

**危险模式1：msgpack 大整数精度丢失**
```python
import msgpack

def process_rpc_data(raw_data):
    data = msgpack.unpackb(raw_data)
    # msgpack 中大于 2^53 的整数可能被转为浮点
    large_id = int(data['id'])  # "12345678901234567890" → float → int 精度丢失
    query(large_id)  # 查询错误的数据
    return large_id

process_rpc_data(b'\x81\xa2id\xcb...')  # 大整数精度丢失
```

**危险模式2：Protobuf 有符号/无符号混淆**
```python
import google.protobuf.json_format

def handle_permissions(json_str):
    msg = MyMessage()
    google.protobuf.json_format.Parse(json_str, msg)
    # 协议定义 uint64，但 JSON 中可能为负数
    perm_mask = msg.permissions  # 负数转无符号后产生巨大值
    if perm_mask & 0x100:
        grant_admin()
    return perm_mask

handle_permissions('{"permissions": -1}')  # -1 转 uint64 后为最大值
```

**危险模式3：Thrift 整数类型不匹配**
```python
from thrift_module import MyService

def rpc_call(client_data):
    # 服务端期望 int32，客户端发送 int64
    result = client.process(client_data)
    index = int(result['value'])  # 截断或溢出
    return array[index]

# 客户端发送 int64(2^40)，服务端接收到截断后的 int32
```

**危险模式4：浮点序列化精度误差**
```python
import pickle

def save_and_load_coordinates():
    coords = [33.33333333, 44.44444444]
    serialized = pickle.dumps(coords)
    loaded = pickle.loads(serialized)
    # 浮点精度累积误差
    index = int(loaded[0] * 100)  # 33.33 * 100 = 3333 或 3332？
    return database[index]

save_and_load_coordinates()  # 浮点误差导致访问错误索引
```

**危险模式5：数组元素类型不一致**
```python
def process_array(json_data):
    import json
    data = json.loads(json_data)
    # JSON 中 [1, 2.5, 3] 的混合类型
    for val in data['numbers']:
        index = int(val)  # 2.5 → 2，类型不一致
        process(array[index])

process_array('{"numbers": [1, 2.5, 3]}')  # 元素类型混合
```

**危险模式6：自定义序列化的类型转换**
```python
class CustomRPC:
    def deserialize(self, data):
        # 自定义协议，第一字节表示类型，后续字节表示值
        type_code = data[0]
        if type_code == 1:  # int32
            value = int.from_bytes(data[1:5], 'big', signed=True)
        elif type_code == 2:  # uint32
            value = int.from_bytes(data[1:5], 'big', signed=False)
        # 类型混淆：客户端发送 uint32，服务端按 int32 解析
        return value

rpc = CustomRPC()
rpc.deserialize(b'\x01\xff\xff\xff\xff')  # -1 vs 4294967295
```

**危险模式7：gRPC 中的类型不匹配**
```python
import grpc
from grpc_module import MyServiceStub

def call_remote_service(channel):
    stub = MyServiceStub(channel)
    # proto3 中，int32/int64 都可以互相赋值
    request = MyRequest(value=2**40)  # 超出 int32 范围
    response = stub.Process(request)
    result = response.result  # int32 截断后的值
    return process(result)

# 客户端发送大数值，服务端接收到截断值
```

### 快速定位核心操作 **[L1-L2]**

**关键词扫描:**
- `msgpack.unpackb()`、`msgpack.packb()` 返回值的类型转换
- `pickle.loads()`、`pickle.dumps()` 的数值处理
- `protobuf` 消息字段的类型转换，特别是有符号/无符号
- `json.loads()` 后的数值直接用于计算或索引
- `thrift` 客户端/服务端消息处理的类型不匹配
- gRPC stub 调用的参数和返回值类型转换
- 自定义序列化协议中的字节到数值的转换
- 跨语言 RPC 中的数值类型映射

**快速定位保护机制 [L2-L3]**
- 反序列化后是否验证数值范围：`if value >= MIN and value <= MAX`
- 是否检查有符号/无符号转换的合理性
- 是否验证浮点数的有限性：`if math.isfinite(val)`
- 是否对数组元素进行类型检查
- 是否使用类型提示或 dataclass 强制类型
- protobuf 消息是否定义了字段校验规则
- 是否在 RPC 层添加类型检查适配器
- 是否对序列化协议进行了版本控制和兼容性检查

---

## Classify

**研判为真漏洞的特征：**
1. 从 msgpack/pickle/JSON 反序列化的数值未检查范围直接用于计算
2. 有符号/无符号类型在序列化/反序列化中混淆，导致值误解
3. 大整数在 RPC 传输中精度丢失或溢出
4. 跨语言 RPC 中数值类型映射错误导致截断
5. 浮点数序列化后的舍入误差用于关键计算
6. 协议字段类型转换后直接用于内存分配或索引

**误报/代码异味的特征：**
- 反序列化后有完整的范围验证
- 使用类型提示或 dataclass 强制类型约束
- 有符号/无符号转换明确处理并有注释
- 大整数使用 `decimal.Decimal` 保留精度
- RPC 框架已处理跨语言类型映射（如 protobuf）
- 序列化协议版本受控且兼容性已验证

---

## Low risk

**以下场景可评为低风险：**

1. **完整的验证**
   - 反序列化后验证范围：`if value >= MIN_VAL and value <= MAX_VAL`
   - 有符号/无符号转换明确处理
   - 浮点数通过 `math.isfinite()` 验证

2. **使用标准库处理**
   - 使用 `protobuf` 等官方库自动处理类型转换
   - 使用 gRPC 框架处理跨语言类型映射
   - `decimal.Decimal` 保留精度

3. **内部受控的数据**
   - 序列化数据来自内部生成，格式已控制
   - 序列化协议版本受控
   - 类型映射明确定义

4. **非关键操作**
   - 数值仅用于显示、日志、统计
   - 不影响内存分配、权限、安全决策

5. **类型提示和检查**
   - 使用 Python 类型提示或 dataclass 强制类型
   - 运行时有类型校验

