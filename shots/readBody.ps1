
$js = @'

(function() {
  const body = document.getElementById('modalBody');
  const mask = document.getElementById('modalMask');
  const bodyHtml = body ? body.innerHTML : '';
  const maskTxt = mask ? (mask.innerText || '').replace(/\s+/g,' ').trim() : '';
  const modal = document.querySelector('.modal') || {};
  return JSON.stringify({maskText: maskTxt.substring(0, 2000), bodyHtmlLen: bodyHtml.length, bodyHtmlSample: bodyHtml.substring(0, 1500)}, null, 2);
})()

'@
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($js))
agent-browser --session bills eval -b $b64
