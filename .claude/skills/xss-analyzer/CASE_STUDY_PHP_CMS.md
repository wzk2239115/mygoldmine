# 案例研究：PHP CMS 中的存储型 XSS 漏洞

> **难度等级：** ★★★☆☆ (中级)
> **审计时间：** 45-60 分钟 (完整链路)
> **框架：** Laravel + Blade 模板

## 漏洞场景

Laravel CMS 允许管理员发布带有富媒体内容的文章。前台显示文章列表和详情。

## 完整漏洞代码

### 后端：Laravel Controller

```php
// app/Http/Controllers/ArticleController.php
class ArticleController extends Controller {
    public function store(Request $request) {
        // ❌ 问题 1：无输入验证或净化
        $article = Article::create([
            'title' => $request->input('title'),
            'content' => $request->input('content'),  // 直接保存
            'author_id' => auth()->id()
        ]);
        return redirect()->route('articles.show', $article);
    }

    public function show(Article $article) {
        return view('articles.show', ['article' => $article]);
    }
}
```

### Blade 模板

```blade
<!-- resources/views/articles/show.blade.php -->
<article>
    <h1>{{ $article->title }}</h1>

    {{-- ✅ 正确：{{ }} 自动转义 --}}
    <div class="author">作者：{{ $article->author->name }}</div>

    {{-- ❌ 问题 2：使用了 {!! !!} 不转义 --}}
    <div class="content">
        {!! $article->content !!}
    </div>

    {{-- 评论列表 --}}
    @foreach($article->comments as $comment)
        <div class="comment">
            {{-- ❌ 同样的问题：使用了 {!! !!} --}}
            <p>{!! $comment->text !!}</p>
        </div>
    @endforeach
</article>
```

### 路由和中间件配置

```php
// routes/web.php
Route::post('/articles', [ArticleController::class, 'store']);
Route::get('/articles/{article}', [ArticleController::class, 'show']);

// ❌ 问题 3：没有 CSRF 保护或其他输入验证中间件
```

## 攻击链路

1. 管理员/编辑发送以下内容：
   ```
   POST /articles
   title=正常标题
   content=<img src=x onerror="alert(document.cookie)">
   ```

2. 内容被直接保存到数据库

3. 用户访问文章页面时：
   ```php
   {!! $article->content !!}  // 输出原始 HTML
   ```

4. 浏览器执行 JavaScript

## 完整修复方案

### 修复 1：后端验证和净化

```php
namespace App\Http\Requests;

use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Support\Str;

class StoreArticleRequest extends FormRequest {
    public function rules() {
        return [
            'title' => 'required|string|max:255',
            'content' => 'required|string|max:10000',
        ];
    }

    public function authorize() {
        return auth()->check() && auth()->user()->isEditor();
    }
}

// Controller
class ArticleController extends Controller {
    public function store(StoreArticleRequest $request) {
        // 验证通过（Laravel 自动验证）

        // 1. 获取已验证的数据
        $validated = $request->validated();

        // 2. 净化 HTML 内容
        $clean = $this->sanitizeHtml($validated['content']);

        // 3. 保存已净化的内容
        $article = Article::create([
            'title' => Str::limit($validated['title'], 255),
            'content' => $clean,  // ✅ 保存已净化的版本
            'author_id' => auth()->id()
        ]);

        return redirect()->route('articles.show', $article);
    }

    private function sanitizeHtml(string $content): string {
        // 使用 HTML Purifier
        $config = \HTMLPurifier_Config::createDefault();
        $config->set('HTML.Allowed', 'p,br,strong,em,u,a[href],img[src|alt]');

        $purifier = new \HTMLPurifier($config);
        return $purifier->purify($content);
    }
}
```

### 修复 2：修正 Blade 模板

```blade
<!-- resources/views/articles/show.blade.php -->
<article>
    {{-- ✅ 使用 {{ }} 自动转义 --}}
    <h1>{{ $article->title }}</h1>

    <div class="author">作者：{{ $article->author->name }}</div>

    {{--
        数据已在后端净化，但我们仍然再次检查
        或改用 {{ strip_tags($article->content) }}
    --}}
    <div class="content">
        {{-- 选项 1：相信后端已净化 --}}
        {!! $article->content !!}

        {{-- 选项 2：再次过滤（防御纵深） --}}
        {{-- {{ strip_tags($article->content, '<p><br><strong><em>') }} --}}

        {{-- 选项 3：存储两个版本 --}}
        {{-- <div>{{ $article->content_plain }}</div> --}}
    </div>

    {{-- 评论 --}}
    @foreach($article->comments as $comment)
        <div class="comment">
            {{-- 评论文本应该用 {{ }} 自动转义 --}}
            <p>{{ $comment->text }}</p>
        </div>
    @endforeach
</article>
```

### 修复 3：使用 Blade 组件和安全包装

```php
// App/View/Components/SafeHtml.php
class SafeHtml extends Component {
    public function __construct(public string $content) {
    }

    public function render() {
        // 净化并标记为安全
        $clean = \Purify::clean($this->content);
        return new HtmlString($clean);
    }
}

// 在模板中使用
<x-safe-html :content="$article->content" />
```

## 审计检查清单

前台审计：
- [ ] 是否使用 `{{ }}` （自动转义）而不是 `{!! !!}` ?
- [ ] 是否使用了 `htmlspecialchars()` 或 `htmlentities()`?

后端审计：
- [ ] 是否对用户输入进行了验证？
- [ ] 是否使用了成熟的净化库（HTML Purifier）?
- [ ] 是否有 CSRF 保护？
- [ ] 是否对文件上传进行了验证？

## 快速修复步骤（15 分钟）

1. 在模板中找到所有 `{!! !!}`
2. 改为 `{{ }}`
3. 部署更改
4. 对现有数据进行清理（数据库脚本）

## 长期修复（1-2 周）

1. 在后端添加 HTML Purifier
2. 迁移现有数据
3. 添加单元测试
4. 部署到生产环境

