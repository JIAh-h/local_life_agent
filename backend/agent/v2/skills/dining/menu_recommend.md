---
name: menu_recommend
description: "根据餐厅和用户偏好推荐菜品"
version: "1.0"
triggers:
  - "推荐菜"
  - "点什么"
  - "招牌菜"
  - "菜单推荐"
  - "吃什么好"
required_tools:
  - get_restaurant_menu
  - get_dish_reviews
input_schema:
  restaurant_id:
    type: string
    required: true
    description: "餐厅ID"
  preferences:
    type: array
    required: false
    description: "口味偏好"
  dietary_restrictions:
    type: array
    required: false
    description: "饮食限制"
  people_count:
    type: integer
    required: false
    default: 2
    description: "用餐人数"
---

## 技能概述

根据餐厅菜单和用户偏好，智能推荐菜品组合。

## 输入规范

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| restaurant_id | string | 是 | 餐厅ID |
| preferences | array | 否 | 口味偏好，如["辣", "清淡"] |
| dietary_restrictions | array | 否 | 饮食限制，如["素食", "无辣"] |
| people_count | integer | 否 | 用餐人数，默认2 |

## 前置条件

- [ ] 已确定目标餐厅（restaurant_id有效）
- [ ] 餐厅有菜单数据

## 执行逻辑

### 步骤1: 获取餐厅菜单

```
调用: get_restaurant_menu(restaurant_id)
返回: menu_data (菜品列表，含名称、价格、分类、销量、评分)
```

### 步骤2: 菜品预筛选

根据条件过滤菜品：
- 排除已售罄菜品
- 应用饮食限制过滤（素食、过敏原等）
- 应用口味偏好过滤

### 步骤3: 菜品评分计算

对每个候选菜品计算推荐分数：
- **热度分**: 销量排名权重 0.3
- **口碑分**: 用户评分权重 0.3
- **招牌分**: 是否招牌菜权重 0.2
- **匹配分**: 与用户偏好匹配度 0.2

### 步骤4: 菜品组合搭配

根据用餐人数生成合理搭配：
- **荤素比例**: 一般 2:1 或 3:2
- **菜量计算**: 人数 + 1~2 道菜
- **汤品/主食**: 根据场景决定是否包含
- **价格控制**: 如有预算要求则控制总价

### 步骤5: 生成推荐话术

为每道推荐菜品生成简短推荐理由。

## 约束条件

1. **菜品数量**: 推荐数量 = 人数 + 1~2
2. **价格约束**: 如有预算，总价不超过预算的120%
3. **多样性**: 同一分类最多推荐2道
4. **时令性**: 优先推荐时令菜品

## 输出格式

```json
{
  "status": "success",
  "data": {
    "restaurant": {
      "id": "rest_001",
      "name": "餐厅名称"
    },
    "recommendations": {
      "dishes": [
        {
          "id": "dish_001",
          "name": "菜品名称",
          "price": 68,
          "category": "热菜",
          "reason": "招牌菜，口碑极佳",
          "tags": ["招牌", "热销"]
        }
      ],
      "total_price": 258,
      "combination": "荤3素2汤1"
    },
    "alternatives": [
      {
        "id": "dish_005",
        "name": "备选菜品",
        "reason": "如不吃辣可选此菜"
      }
    ]
  },
  "message": "为您推荐 {count} 道菜品，预计人均 {price} 元"
}
```

## 异常处理

| 错误码 | 说明 | 处理方式 |
|--------|------|----------|
| E001 | 菜单获取失败 | 提示用户查看纸质菜单 |
| E002 | 无符合条件菜品 | 放宽筛选条件重新推荐 |
| E003 | 餐厅不存在 | 提供附近其他餐厅 |

## 对话示例

**用户**: 这家店两个人吃什么好？

**解析**:
- restaurant_id: 当前查看的餐厅
- people_count: 2
- preferences: []

**输出**: 推荐3-4道菜品，包含招牌菜和荤素搭配，预计人均价格。
