/* Native source disclosure works without scripts; enhance dismissal and selection feedback. */
(() => {
  const dropdown=document.querySelector('.source-dropdown');
  if(!dropdown)return;
  const summary=dropdown.querySelector('summary');
  function update() {
    const count=dropdown.querySelectorAll('input[name=sources]:checked').length;
    dropdown.querySelector('#source-filter-value').textContent=count?`${count} 件を選択`:'すべての情報源';
  }
  dropdown.addEventListener('change',update);
  dropdown.addEventListener('keydown',event=>{
    if(event.key==='Escape' && dropdown.open){event.preventDefault();dropdown.open=false;summary.focus();}
  });
  document.addEventListener('click',event=>{if(!dropdown.contains(event.target))dropdown.open=false;});
  update();
})();
