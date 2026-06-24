---
name: {{skill_name}}
description: {{简短描述，用于Resolver语义匹配}}
version: "1.0"
author: "{{作者}}"
triggers:
  - "{{触发关键词1}}"
  - "{{触发关键词2}}"
required_tools:
  - {{工具名称1}}
  - {{工具名称2}}
input_schema:
  param1:
    type: string
    required: true
    description: "参数说明"
  param2:
    type: integer
    required: false
    default: 10
    description: "参数说明"
---

## 技能概述

{{一句话描述这个技能做什么}}

## 输入规范

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| param1 | string | 是 | 参数说明 |
| param2 | integer | 否 | 参数说明，默认10 |

## 前置条件

- [ ] 条件1：描述
- [ ] 条件2：描述

## 执行逻辑

### 步骤1: 验证输入

检查输入参数的完整性和合法性：
- 验证 param1 不为空
- 验证 param2 在有效范围内

### 步骤2: 数据准备

调用确定性工具准备数据：
```
调用: query_database(param1)
返回: data_list
```

### 步骤3: 核心处理

根据业务逻辑处理数据：
- 条件A → 执行路径X
- 条件B → 执行路径Y

### 步骤4: 结果组装

将处理结果组装为标准输出格式。

## 约束条件

1. **数据约束**: 描述
2. **业务约束**: 描述
3. **性能约束**: 描述

## 输出格式

```json
{
  "status": "success",
  "data": {
    "key1": "value1",
    "key2": "value2"
  },
  "message": "操作成功描述"
}
```

## 异常处理

| 错误码 | 说明 | 处理方式 |
|--------|------|----------|
| E001 | 参数错误 | 返回参数校验失败详情 |
| E002 | 数据不存在 | 返回空结果并提示 |
| E003 | 系统异常 | 记录日志并返回通用错误 |

## 示例

**输入**:
```json
{
  "param1": "示例值",
  "param2": 5
}
```

**输出**:
```json
{
  "status": "success",
  "data": {
    "result": "处理结果"
  }
}
```
