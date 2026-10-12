(function () {
  var root = document.querySelector('[data-reader]');
  if (!root) return;
  var cards = Array.prototype.slice.call(document.querySelectorAll('.article-card[data-article-id]'));
  if (!cards.length) return;

  var focusIndex = 0;
  var openId = root.getAttribute('data-open-article');
  if (openId) {
    for (var i = 0; i < cards.length; i++) {
      if (cards[i].getAttribute('data-article-id') === openId) {
        focusIndex = i;
        break;
      }
    }
  }

  function paint() {
    cards.forEach(function (card, index) {
      card.classList.toggle('keyboard-focus', index === focusIndex);
    });
    var active = cards[focusIndex];
    if (active && typeof active.scrollIntoView === 'function') {
      active.scrollIntoView({ block: 'nearest' });
    }
  }

  function openFocused() {
    var card = cards[focusIndex];
    if (!card) return;
    var form = card.querySelector('form.open-form');
    if (form) {
      form.requestSubmit ? form.requestSubmit() : form.submit();
      return;
    }
    var link = card.querySelector('a.article-title');
    if (link) link.click();
  }

  function submitAction(action, preferUnreadNext) {
    var card = cards[focusIndex];
    if (!card) return;
    var selector = action === 'read'
      ? (preferUnreadNext ? 'form[data-scan-read]' : 'form[action*="/read"]')
      : 'form[action*="/star"]';
    var form = card.querySelector(selector) || document.querySelector('.article-detail ' + selector);
    if (form) {
      form.requestSubmit ? form.requestSubmit() : form.submit();
    }
  }

  function nextUnread() {
    for (var offset = 1; offset <= cards.length; offset++) {
      var index = (focusIndex + offset) % cards.length;
      if (cards[index].getAttribute('data-read') === '0') {
        focusIndex = index;
        paint();
        openFocused();
        return;
      }
    }
  }

  paint();

  document.addEventListener('keydown', function (event) {
    var tag = (event.target && event.target.tagName) || '';
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || event.target.isContentEditable) {
      if (event.key === 'Escape') event.target.blur();
      return;
    }
    if (event.altKey || event.ctrlKey || event.metaKey) return;

    if (event.key === 'j' || event.key === 'J') {
      event.preventDefault();
      focusIndex = Math.min(cards.length - 1, focusIndex + 1);
      paint();
    } else if (event.key === 'k' || event.key === 'K') {
      event.preventDefault();
      focusIndex = Math.max(0, focusIndex - 1);
      paint();
    } else if (event.key === 'o' || event.key === 'Enter') {
      event.preventDefault();
      openFocused();
    } else if (event.key === 'm' || event.key === 'M') {
      event.preventDefault();
      submitAction('read', true);
    } else if (event.key === 's' || event.key === 'S') {
      event.preventDefault();
      submitAction('star', false);
    } else if (event.key === 'n' || event.key === 'N') {
      event.preventDefault();
      nextUnread();
    } else if (event.key === '/') {
      var search = document.getElementById('search');
      if (search) {
        event.preventDefault();
        search.focus();
        search.select();
      }
    }
  });
})();
