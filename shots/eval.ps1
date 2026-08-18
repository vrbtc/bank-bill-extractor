
$js = @'
(function(){
  const cards = document.querySelectorAll('.stat-card');
  const stats = [];
  cards.forEach(c => stats.push(c.innerText.replace(/\s+/g, ' ').trim()));
  const hero = document.querySelector('.hero') ? document.querySelector('.hero').innerText.replace(/\s+/g, ' ').trim() : '(no hero)';
  const nextBtn = document.querySelector('[data-action="next-month"], .cal-nav button:last-child, #nextMonth');
  const calTitle = document.getElementById('calTitle').innerText.replace(/\s+/g, ' ').trim();
  return JSON.stringify({stats, hero, calTitle}, null, 2);
})()
'@
$bytes = [System.Text.Encoding]::UTF8.GetBytes($js)
$b64 = [Convert]::ToBase64String($bytes)
agent-browser --session bills eval -b $b64
