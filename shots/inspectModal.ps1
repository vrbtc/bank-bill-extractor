
$js = @'

(function() {
  // 列出所有弹窗/遮罩/面板 类名包含 modal/dialog/popup/detail 的元素
  const all = document.querySelectorAll('*');
  const candidates = [];
  for (const el of all) {
    const cls = (el.className && typeof el.className === 'string') ? el.className : '';
    const id = el.id || '';
    const role = el.getAttribute && el.getAttribute('role') || '';
    if (/modal|dialog|popup|detail|overlay/.test(cls + ' ' + id + ' ' + role)) {
      const t = (el.innerText || '').replace(/\s+/g,' ').trim();
      candidates.push({tag: el.tagName, cls, id, role, text: t.substring(0, 800)});
    }
  }
  // 也直接用 body 全部文本
  const full = document.body.innerText.replace(/\s+/g,' ').trim();
  // 截取 "日期详情" 附近 1500 字符
  const idx = full.indexOf('日期详情');
  const around = idx >= 0 ? full.substring(Math.max(0, idx - 50), idx + 2000) : '(not found)';
  return JSON.stringify({candidates, aroundModalText: around}, null, 2);
})()

'@
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($js))
agent-browser --session bills eval -b $b64
