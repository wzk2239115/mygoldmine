# XSS Sink测试文件 - Python
from flask import Flask, render_template, render_template_string, request, Response

app = Flask(__name__)

@app.route('/test')
def test_xss_sinks():
    # 直接输出到响应（危险）
    user_input = request.args.get('user_input')
    response = Response()
    response.write(user_input)

    # 模板渲染（某些框架可能转义，但需要监控）
    data = request.form.get('data')
    rendered = render_template('template.html', content=data)

    # 使用render_template_string（高危）
    template_str = request.args.get('template')
    output = render_template_string(template_str)

    # 动态代码执行（极高危）
    code = request.args.get('code')
    eval(code)

    # 字符串操作（会被检测）
    name = request.args.get('name')
    message = str(name).format(request.args.get('format_arg'))

    return "OK"

@app.route('/flask_output')
def flask_output():
    # Flask response对象
    response = Response()
    response.set_data(request.args.get('data'))
    response.set_cookie('name', request.args.get('cookie_value'))
    return response
