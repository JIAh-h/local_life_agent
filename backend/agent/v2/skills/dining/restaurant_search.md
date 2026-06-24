---
name: restaurant_search
description: "搜索餐厅，支持按位置、菜系、价格、评分等条件筛选"
version: "1.0"
triggers:
  - "找餐厅"
  - "推荐餐厅"
  - "附近餐厅"
  - "吃什么"
  - "餐厅搜索"
required_tools:
  - amap.place_around
  - amap.regeocode
input_schema:
  location:
    type: object
    required: true
    description: "用户位置 {lat, lng, address}"
  cuisine:
    type: string
    required: false
    description: "菜系类型"
  price_range:
    type: string
    required: false
    enum: ["low", "medium", "high", "luxury"]
    description: "价格区间"
  distance:
    type: integer
    required: false
    default: 3000
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

根据用户位置和偏好条件搜索附近餐厅，返回筛选后的推荐列表。

## 输入规范

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| location | object | 是 | 用户位置，包含 lat, lng, address |
| cuisine | string | 否 | 菜系类型（如：川菜、日料、西餐） |
| price_range | string | 否 | 价格区间：low/medium/high/luxury |
| distance | integer | 否 | 搜索半径，默认3000米 |
| rating_min | float | 否 | 最低评分，默认4.0 |
| limit | integer | 否 | 返回数量，默认5 |

## 前置条件

- [ ] 用户已提供位置信息或系统可获取用户位置
- [ ] 位置坐标有效（纬度-90~90，经度-180~180）

## 执行逻辑

### 步骤1: 参数标准化

将自然语言描述转换为标准参数：
- "附近" → distance=1000
- "步行可达" → distance=500
- "便宜" → price_range="low"
- "高档" → price_range="high"
- 菜系关键词提取：川、粤、日、韩、西、意等

### 步骤2: 构建搜索条件

```
search_params = {
    "location": "{lat},{lng}",
    "radius": distance,
    "type": "restaurant",
    "keyword": cuisine,
    "sort_rule": "distance"
}
```

### 步骤3: 调用确定性工具搜索

```
调用: amap.place_around(search_params)
返回: raw_results (POI列表)
```

### 步骤4: 结果筛选与排序

按以下优先级筛选和排序：
1. **评分筛选**: rating >= rating_min
2. **价格匹配**: 如指定price_range则过滤
3. **综合排序**: 评分权重0.6 + 距离权重0.4

### 步骤5: 结果增强

对top N结果进行信息补充：
```
调用: amap.regeocode(latitude, longitude)
返回: 详细地址信息
```

### 步骤6: 组装输出

将筛选后的结果组装为标准推荐格式。

## 约束条件

1. **位置约束**: 必须有有效的位置信息
2. **数量约束**: 单次最多返回10个结果
3. **距离约束**: 最大搜索半径50km
4. **实时性**: 优先返回当前营业的餐厅

## 输出格式

```json
{
  "status": "success",
  "data": {
    "restaurants": [
      {
        "id": "rest_001",
        "name": "餐厅名称",
        "cuisine": "菜系",
        "rating": 4.5,
        "price_level": "medium",
        "distance": 500,
        "address": "详细地址",
        "phone": "联系电话",
        "hours": "营业时间",
        "highlights": ["招牌菜1", "招牌菜2"],
        "is_open": true
      }
    ],
    "total": 5,
    "search_params": {
      "location": "用户位置",
      "cuisine": "筛选菜系",
      "radius": 3000
    }
  },
  "message": "为您找到 {count} 家符合条件的餐厅"
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

**用户**: 附近有什么好吃的川菜馆？

**解析**:
- location: 用户当前位置
- cuisine: "川菜"
- distance: 1000 (附近)
- rating_min: 4.0 (好吃)

**输出**: 推荐5家附近评分4.0以上的川菜馆，包含名称、距离、评分、人均价格、招牌菜。

---

**用户**: 找个安静的地方请客吃饭，人均200左右

**解析**:
- location: 用户当前位置
- price_range: "high" (人均200)
- tags: ["安静", "适合聚餐"]

**输出**: 推荐5家环境安静、适合商务宴请的中高端餐厅。
