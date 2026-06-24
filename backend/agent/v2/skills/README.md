# Skills Directory - Fat Skills 架构

## 设计理念

**Thin Harness, Fat Skills（轻驾驭、重技能）**

将业务逻辑下沉到结构化的Markdown文档中，让LLM能够精准聚焦执行。

## 目录结构

```
skills/
├── README.md              # 本文件
├── _templates/            # 技能模板
│   └── skill_template.md
├── dining/                # 餐饮相关技能
│   ├── restaurant_search.md
│   └── menu_recommend.md
├── attractions/           # 景点相关技能
│   ├── attraction_search.md
│   └── attraction_recommend.md
├── travel/                # 旅行相关技能（规划中）
│   ├── itinerary_plan.md
│   └── hotel_search.md
├── lifestyle/             # 生活服务技能（规划中）
│   ├── movie_booking.md
│   └── fitness_class.md
└── general/               # 通用技能
    ├── chitchat.md
    └── faq.md
```

## Skill Markdown 规范

每个Skill文件必须包含以下部分：

### 1. Front Matter（元数据）
```yaml
---
name: skill_name
description: 技能描述（用于Resolver匹配）
version: "1.0"
triggers:
  - "触发词1"
  - "触发词2"
required_tools:
  - tool_name_1
  - tool_name_2
---
```

### 2. 正文结构

```markdown
## 输入规范
描述技能需要的输入参数和格式

## 前置条件
执行前必须满足的条件

## 执行逻辑
### 步骤1: xxx
### 步骤2: xxx
### 步骤N: xxx

## 约束条件
执行过程中的限制和边界

## 输出格式
期望的输出格式和结构
```

## 添加新技能

1. 在对应类别目录下创建 `.md` 文件
2. 按照规范填写Front Matter和正文
3. 系统会自动发现和加载新技能

## 动态热加载

Skill文件支持动态热加载，无需重启服务即可生效。
