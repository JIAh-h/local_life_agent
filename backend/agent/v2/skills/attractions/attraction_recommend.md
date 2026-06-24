---
name: attraction_recommend
description: "根据场景和偏好推荐景点，支持亲子游、周末出游、约会等场景"
version: "1.0"
triggers:
  - "周末去哪"
  - "带孩子玩"
  - "约会地点"
  - "拍照打卡"
  - "户外活动"
  - "踏青"
  - "赏花"
  - "爬山"
required_tools:
  - amap.place_around
  - weather.current
input_schema:
  location:
    type: object
    required: true
    description: "用户位置 {lat, lng, address}"
  scenario:
    type: string
    required: false
    description: "出游场景"
  preferences:
    type: array
    required: false
    description: "偏好标签"
  people_count:
    type: integer
    required: false
    default: 2
    description: "出行人数"
  has_children:
    type: boolean
    required: false
    default: false
    description: "是否有儿童同行"
---

## 技能概述

根据用户场景和偏好，智能推荐适合的景点和出游方案。

## 输入规范

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| location | object | 是 | 用户位置，包含 lat, lng, address |
| scenario | string | 否 | 出游场景：亲子游、约会、朋友聚会、独自散心、摄影采风 |
| preferences | array | 否 | 偏好标签：["自然", "人文", "刺激", "安静", "网红"] |
| people_count | integer | 否 | 出行人数，默认2 |
| has_children | boolean | 否 | 是否有儿童同行，默认false |

## 前置条件

- [ ] 用户已提供位置信息或系统可获取用户位置
- [ ] 位置坐标有效

## 执行逻辑

### 步骤1: 场景分析

根据场景确定推荐策略：
- **亲子游**: 选择有儿童设施、安全性高的公园、动物园、科技馆
- **约会**: 选择环境优美、氛围浪漫的景点，如湖边、花园、特色街区
- **朋友聚会**: 选择可互动、有趣的场所，如主题公园、户外拓展
- **独自散心**: 选择安静、适合冥想的自然景点
- **摄影采风**: 选择风景优美、有特色的打卡点

### 步骤2: 查询天气

```
调用: weather.current(city)
返回: weather_info (天气信息)
```

根据天气调整推荐：
- 晴天: 推荐户外景点
- 雨天: 推荐室内景点或多雨备用方案
- 高温: 推荐有遮阴或室内景点

### 步骤3: 景点搜索

```
search_params = {
    "location": "{lat},{lng}",
    "radius": 10000,
    "types": "风景名胜",
    "keywords": scenario_keywords
}
```

### 步骤4: 智能筛选

根据场景和偏好筛选：
1. **安全性**: 有儿童时排除危险景点
2. **适合度**: 匹配场景需求
3. **便利性**: 考虑交通、停车、餐饮配套

### 步骤5: 生成出游方案

为推荐景点生成完整出游建议：
- 推荐游玩时长
- 最佳游玩时段
- 注意事项
- 周边配套（餐饮、卫生间等）

## 约束条件

1. **天气适配**: 根据天气推荐室内/室外景点
2. **安全优先**: 有儿童时优先推荐安全性高的景点
3. **距离合理**: 推荐景点距离不超过30km
4. **多样性**: 同类型景点最多推荐2个

## 输出格式

```json
{
  "status": "success",
  "data": {
    "weather": {
      "condition": "晴",
      "temperature": "25°C",
      "suggestion": "适合户外活动"
    },
    "recommendations": [
      {
        "name": "景点名称",
        "type": "景点类型",
        "rating": 4.6,
        "distance": 5000,
        "scenario_match": "亲子游",
        "highlights": ["儿童乐园", "野餐区", "停车场"],
        "suggested_duration": "3-4小时",
        "best_time": "上午9-11点",
        "tips": "建议自带食物和水",
        "nearby": {
          "food": "附近500米有餐厅",
          "restroom": "园区内有3处卫生间"
        }
      }
    ],
    "plan_summary": "为您推荐 {count} 个适合{scenario}的景点"
  },
  "message": "根据您的需求，为您推荐以下景点"
}
```

## 异常处理

| 错误码 | 说明 | 处理方式 |
|--------|------|----------|
| E001 | 位置信息缺失 | 提示用户开启定位或手动输入位置 |
| E002 | 天气查询失败 | 跳过天气推荐，直接推荐景点 |
| E003 | 无匹配景点 | 扩大搜索范围或调整场景 |

## 对话示例

**用户**: 周末带孩子去哪里玩比较好？

**解析**:
- location: 用户当前位置
- scenario: "亲子游"
- has_children: true
- preferences: ["儿童友好", "安全"]

**输出**: 查询天气，推荐3-5个适合亲子游玩的景点，包含儿童设施介绍、游玩时长建议、注意事项。

---

**用户**: 想找一个安静的地方拍照

**解析**:
- location: 用户当前位置
- scenario: "摄影采风"
- preferences: ["安静", "风景优美", "适合拍照"]

**输出**: 推荐3-5个适合拍照的安静景点，包含最佳拍摄时间、拍摄建议。
