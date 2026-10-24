(() => {
  const picker=document.querySelector('#provider-picker'), select=picker?.querySelector('select');
  if(!select)return;
  select.addEventListener('change',()=>picker.requestSubmit());
  // Preserve a selection made while deferred scripts/styles were loading.
  const shown=document.querySelector('form[method=post] input[name=provider]')?.value;
  if(shown && shown!==select.value)picker.requestSubmit();
})();
