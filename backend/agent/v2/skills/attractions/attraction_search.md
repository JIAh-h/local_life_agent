---
name: attraction_search
description: "搜索周边景点，支持按类型、距离、评分等条件筛选"
version: "1.0"
triggers:
  - "景点"
  - "旅游"
  - "游玩"
  - "去哪里玩"
  - "附近景点"
  - "推荐景点"
  - "风景"
  - "公园"
  - "名胜"
required_tools:
  - amap.place_around
  - amap.regeocode
input_schema:
  location:
    type: object
    required: true
    description: "用户位置 {lat, lng, address}"
  attraction_type:
    type: string
    required: false
    description: "景点类型"
  distance:
    type: integer
    required: false
    default: 5000
    description: "搜索半径(米)"
  rating_min:
    type: float
    required: false
    default: 4.0
    description: "最低评分"
  limit:
    type: integer
    required: false
    default: 5
    description: "返回数量"
---

## 技能概述

根据用户位置和偏好条件搜索附近景点，返回筛选后的推荐列表。

## 输入规范

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| location | object | 是 | 用户位置，包含 lat, lng, address |
| attraction_type | string | 否 | 景点类型（如：公园、博物馆、历史古迹、自然风光） |
| distance | integer | 否 | 搜索半径，默认5000米 |
| rating_min | float | 否 | 最低评分，默认4.0 |
| limit | integer | 否 | 返回数量，默认5 |

## 前置条件

- [ ] 用户已提供位置信息或系统可获取用户位置
- [ ] 位置坐标有效（纬度-90~90，经度-180~180）

## 执行逻辑

### 步骤1: 参数标准化

将自然语言描述转换为标准参数：
- "附近" → distance=3000
- "步行可达" → distance=1000
- "开车" → distance=10000
- 景点类型关键词提取：公园、博物馆、历史、自然、古镇、寺庙等

### 步骤2: POI 类型映射

根据景点类型选择高德 POI 类型编码：
- 景点/风景名胜 → `风景名胜` 或 `110000`
- 公园/广场 → `公园广场` 或 `110100`
- 博物馆 → `博物馆` 或 `141200`
- 历史古迹 → `风景名胜;风景名胜相关;文化古迹` 或 `110200`
- 自然风光 → `风景名胜;自然景观` 或 `110100`

### 步骤3: 构建搜索条件

```
search_params = {
    "location": "{lat},{lng}",
    "radius": distance,
    "types": attraction_type,
    "keywords": keywords,
    "sort_rule": "distance"
}
```

### 步骤4: 调用确定性工具搜索

```
调用: amap.place_around(search_params)
返回: raw_results (POI列表)
```

### 步骤5: 结果筛选与排序

按以下优先级筛选和排序：
1. **评分筛选**: rating >= rating_min
2. **类型匹配**: 如指定attraction_type则过滤
3. **综合排序**: 评分权重0.6 + 距离权重0.4

### 步骤6: 结果增强

对top N结果进行信息补充：
```
调用: amap.regeocode(latitude, longitude)
返回: 详细地址信息
```

### 步骤7: 组装输出

将筛选后的结果组装为标准推荐格式。

## 约束条件

1. **位置约束**: 必须有有效的位置信息
2. **数量约束**: 单次最多返回10个结果
3. **距离约束**: 最大搜索半径50km
4. **实时性**: 优先返回当前开放的景点

## 输出格式

```json
{
  "status": "success",
  "data": {
    "attractions": [
      {
        "id": "attr_001",
        "name": "景点名称",
        "type": "景点类型",
        "rating": 4.5,
        "distance": 2000,
        "address": "详细地址",
        "phone": "联系电话",
        "hours": "开放时间",
        "highlights": ["特色1", "特色2"],
        "is_open": true
      }
    ],
    "total": 5,
    "search_params": {
      "location": "用户位置",
      "attraction_type": "筛选类型",
      "radius": 5000
    }
  },
  "message": "为您找到 {count} 个符合条件的景点"
}
```

## 异常处理

| 错误码 | 说明 | 处理方式 |
|--------|------|----------|
| E001 | 位置信息缺失 | 提示用户开启定位或手动输入位置 |
| E002 | 搜索无结果 | 扩大搜索范围或放宽筛选条件 |
| E003 | POI服务异常 | 返回缓存数据或提示稍后重试 |
| E004 | 详情获取失败 | 使用基础信息展示 |

## 对话示例

**用户**: 附近有什么好玩的景点？

**解析**:
- location: 用户当前位置
- distance: 5000 (附近)
- rating_min: 4.0 (好玩)

**输出**: 推荐5个附近评分4.0以上的景点，包含名称、距离、评分、开放时间、特色亮点。

---

**用户**: 带孩子去公园玩，哪里合适？

**解析**:
- location: 用户当前位置
- attraction_type: "公园"
- keywords: "亲子,儿童"

**输出**: 推荐5个适合亲子游玩的公园，包含设施介绍、距离、评分。
