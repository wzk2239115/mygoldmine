<?php
// XSS Sink测试文件 - PHP

// 直接输出函数（危险）
echo $_GET['user_input'];
echo "Hello " . $_POST['name'];
print $_SESSION['message'];

// 模板渲染（虽然可能转义，但需要监控）
view('template.blade.php', ['data' => $_GET['data']]);
render('page.html', ['content' => $_POST['content']]);

// 动态代码执行（高危）
eval('$x = ' . $_GET['code'] . ';');

// 输出缓冲
ob_start();
echo $_GET['buffer_content'];
$output = ob_get_contents();

// 安全的实践（但仍会被检测因为函数本身是Sink）
echo htmlspecialchars($_GET['safe'], ENT_QUOTES, 'UTF-8');
?>
