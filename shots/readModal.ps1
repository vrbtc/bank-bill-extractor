
$js = @'

(function() {
  const modal = document.querySelector('.modal, [role=dialog], .popup, .day-detail, [class*=modal]') || document.body;
  return modal.innerText.replace(/\s+/g,' ').trim();
})()

'@
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($js))
agent-browser --session bills eval -b $b64
