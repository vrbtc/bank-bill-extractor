
$js = @'

(function() {
  const result = [];
  const all = document.querySelectorAll('*');
  for (const el of all) {
    if (el.children && el.children.length) continue;
    const t = (el.textContent || '').replace(/\s+/g,' ').trim();
    if (/2\.8k|2,833|车贷/.test(t)) {
      const parent = el.parentElement;
      const gc = el.closest && (el.closest('td') || el.closest('[role=gridcell]') || el.closest('[class*=day]') || el.closest('[class*=cell]'));
      const candidate = gc || parent;
      const cls = (candidate && candidate.className) || '';
      result.push({leafText: t.substring(0, 50), candidateCls: String(cls).substring(0, 200), rect: candidate && candidate.getBoundingClientRect && Object.assign({}, candidate.getBoundingClientRect())});
      if (result.length >= 8) break;
    }
  }
  return JSON.stringify(result, null, 2);
})()

'@
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($js))
agent-browser --session bills eval -b $b64
