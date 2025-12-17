// XSS Sink测试文件 - JavaScript

// innerHTML - 高危
const userInput = getUserInput();
document.getElementById('content').innerHTML = userInput;

// outerHTML - 高危
element.outerHTML = '<div>' + userInput + '</div>';

// document.write - 危险（已过时）
document.write('<h1>' + userInput + '</h1>');

// insertAdjacentHTML - 高危
element.insertAdjacentHTML('beforeend', userInput);

// eval - 极高危
eval(userInput);

// Function构造函数 - 高危
const dynamicFunc = new Function('return ' + userInput);

// setTimeout/setInterval with string - 危险（已过时）
setTimeout('alert(' + userInput + ')', 1000);
setInterval('updateContent(' + userInput + ')', 5000);

// textContent - 低风险（自动转义）
element.textContent = userInput;

// 常见的安全实践（但仍会被Sink检测）
element.textContent = userInput;  // 安全
const encoded = encodeURIComponent(userInput);
const escaped = htmlEscape(userInput);
