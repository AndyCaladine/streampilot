(function () {
  'use strict';

  const codeInput      = document.getElementById('code');
  const validateBtn    = document.getElementById('validateCodeBtn');
  const regForm        = document.getElementById('regForm');
  const codeIndicator  = document.getElementById('codeIndicator');
  const codeHint       = document.getElementById('codeHint');
  const codeValidBadge = document.getElementById('codeValidatedBadge');
  const submitBtn      = document.getElementById('submitBtn');

  const emailInput         = document.getElementById('email');
  const emailConfirm       = document.getElementById('email_confirm');
  const emailIndicator     = document.getElementById('emailMatchIndicator');
  const emailMatchHint     = document.getElementById('emailMatchHint');

  const passwordInput          = document.getElementById('password');
  const passwordConfirm        = document.getElementById('password_confirm');
  const passwordMatchIndicator = document.getElementById('passwordMatchIndicator');
  const passwordMatchHint      = document.getElementById('passwordMatchHint');
  const strengthPanel          = document.getElementById('passwordStrength');

  const consentData    = document.getElementById('consent_data');
  const consentTwitch  = document.getElementById('consent_twitch');

  let codeValidated  = false;
  let emailsMatch    = false;
  let passwordOk     = false;
  let passwordsMatch = false;

  // ---- Code length indicator --------------------------------
  codeInput.addEventListener('input', function () {
    codeIndicator.classList.toggle('visible', this.value.length >= 8);
  });

  // ---- Validate code via fetch ------------------------------
  validateBtn.addEventListener('click', function () {
    const code = codeInput.value.trim();

    if (code.length < 8) {
      codeHint.textContent = 'Code must be at least 8 characters.';
      codeHint.style.color = 'var(--danger)';
      return;
    }

    validateBtn.textContent = 'Checking...';
    validateBtn.disabled = true;

    fetch('/validate-code', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: code })
    })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (data.valid) {
        codeValidated = true;
        codeInput.readOnly = true;
        codeIndicator.classList.add('visible');
        codeHint.textContent = '';
        validateBtn.style.display = 'none';
        codeValidBadge.style.display = 'flex';
        regForm.classList.add('visible');
        checkSubmitReady();
      } else {
        codeHint.textContent = data.message || 'That code is invalid or has already been used.';
        codeHint.style.color = 'var(--danger)';
        validateBtn.textContent = 'Validate Code';
        validateBtn.disabled = false;
      }
    })
    .catch(function () {
      codeHint.textContent = 'Something went wrong. Please try again.';
      codeHint.style.color = 'var(--danger)';
      validateBtn.textContent = 'Validate Code';
      validateBtn.disabled = false;
    });
  });

  // ---- Email match indicator --------------------------------
  function checkEmailMatch() {
    var a = emailInput.value.trim().toLowerCase();
    var b = emailConfirm.value.trim().toLowerCase();

    if (!b) {
      emailIndicator.classList.remove('visible');
      emailMatchHint.textContent = '';
      emailsMatch = false;
      checkSubmitReady();
      return;
    }

    if (a === b) {
      emailIndicator.classList.add('visible');
      emailMatchHint.textContent = 'Emails match.';
      emailMatchHint.style.color = 'var(--accent)';
      emailsMatch = true;
    } else {
      emailIndicator.classList.remove('visible');
      emailMatchHint.textContent = 'Emails do not match.';
      emailMatchHint.style.color = 'var(--danger)';
      emailsMatch = false;
    }
    checkSubmitReady();
  }

  emailInput.addEventListener('input', checkEmailMatch);
  emailConfirm.addEventListener('input', checkEmailMatch);

  // ---- Password strength ------------------------------------
  var rules = {
    lower:   { re: /[a-z]/,        el: document.getElementById('rule-lower')   },
    upper:   { re: /[A-Z]/,        el: document.getElementById('rule-upper')   },
    number:  { re: /[0-9]/,        el: document.getElementById('rule-number')  },
    special: { re: /[^A-Za-z0-9]/, el: document.getElementById('rule-special') },
    length:  { re: /.{8,}/,        el: document.getElementById('rule-length')  }
  };

  var bars = [
    document.getElementById('bar1'),
    document.getElementById('bar2'),
    document.getElementById('bar3'),
    document.getElementById('bar4')
  ];

  function updateRule(rule, met) {
    var el    = rule.el;
    var check = el.querySelector('.check-path');
    var dot   = el.querySelector('.dot');
    el.classList.toggle('met', met);
    if (check) check.setAttribute('opacity', met ? '1' : '0');
    if (dot)   dot.setAttribute('opacity',   met ? '0' : '1');
  }

  passwordInput.addEventListener('input', function () {
    var val = this.value;

    if (!val.length) {
      strengthPanel.style.display = 'none';
      passwordOk = false;
      checkSubmitReady();
      return;
    }

    strengthPanel.style.display = 'block';

    var score = 0;
    Object.values(rules).forEach(function (rule) {
      var met = rule.re.test(val);
      updateRule(rule, met);
      if (met) score++;
    });

    bars.forEach(function (b) { b.className = 'strength-bar'; });

    var barClass = score <= 1 ? 'active-weak'
                 : score <= 2 ? 'active-fair'
                 : score <= 3 ? 'active-good'
                 : 'active-strong';

    for (var i = 0; i < Math.min(score, 4); i++) {
      bars[i].classList.add(barClass);
    }

    passwordOk = (score === 5);
    checkPasswordMatch();
    checkSubmitReady();
  });

  // ---- Password confirm match indicator ---------------------
  function checkPasswordMatch() {
    var a = passwordInput.value;
    var b = passwordConfirm.value;

    if (!b) {
      passwordMatchIndicator.classList.remove('visible');
      passwordMatchHint.textContent = '';
      passwordsMatch = false;
      checkSubmitReady();
      return;
    }

    if (a === b) {
      passwordMatchIndicator.classList.add('visible');
      passwordMatchHint.textContent = 'Passwords match.';
      passwordMatchHint.style.color = 'var(--accent)';
      passwordsMatch = true;
    } else {
      passwordMatchIndicator.classList.remove('visible');
      passwordMatchHint.textContent = 'Passwords do not match.';
      passwordMatchHint.style.color = 'var(--danger)';
      passwordsMatch = false;
    }
    checkSubmitReady();
  }

  passwordConfirm.addEventListener('input', checkPasswordMatch);

  // ---- Consent listeners ------------------------------------
  consentData.addEventListener('change', checkSubmitReady);
  consentTwitch.addEventListener('change', checkSubmitReady);

  // ---- Enable submit when all conditions met ----------------
  function checkSubmitReady() {
    submitBtn.disabled = !(
      codeValidated  &&
      emailsMatch    &&
      passwordOk     &&
      passwordsMatch &&
      consentData.checked &&
      consentTwitch.checked
    );
  }

  // ---- Privacy modal ----------------------------------------
  function openPrivacyModal(e) {
    if (e) e.preventDefault();
    document.getElementById('privacyModal').classList.add('open');
  }

  function closePrivacyModal() {
    document.getElementById('privacyModal').classList.remove('open');
  }

  document.querySelectorAll('.privacy-modal-trigger').forEach(function (el) {
    el.addEventListener('click', openPrivacyModal);
  });

  document.getElementById('privacyModalClose').addEventListener('click', closePrivacyModal);
  document.getElementById('privacyModalAccept').addEventListener('click', closePrivacyModal);

  document.getElementById('privacyModal').addEventListener('click', function (e) {
    if (e.target === this) closePrivacyModal();
  });

})();