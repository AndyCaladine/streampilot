/* =============================================================
   password_strength.js — standalone password strength checker
   Works on change_password.html and reset_password.html
   ============================================================= */

document.addEventListener("DOMContentLoaded", () => {
  const passwordInput = document.getElementById("new_password");
  const confirmInput  = document.getElementById("confirm_password");
  const strengthPanel = document.getElementById("passwordStrength");
  const confirmHint   = document.getElementById("confirmHint");

  const bars = [
    document.getElementById("bar1"),
    document.getElementById("bar2"),
    document.getElementById("bar3"),
    document.getElementById("bar4"),
  ];

  const rules = {
    lower:   { re: /[a-z]/,        id: "rule-lower"   },
    upper:   { re: /[A-Z]/,        id: "rule-upper"   },
    number:  { re: /[0-9]/,        id: "rule-number"  },
    special: { re: /[^A-Za-z0-9]/, id: "rule-special" },
    length:  { re: /.{8,}/,        id: "rule-length"  },
  };

  if (!passwordInput) return;

  passwordInput.addEventListener("input", () => {
    const val = passwordInput.value;

    if (!val.length) {
      if (strengthPanel) strengthPanel.style.display = "none";
      return;
    }

    if (strengthPanel) strengthPanel.style.display = "block";

    let score = 0;
    Object.values(rules).forEach(rule => {
      const met = rule.re.test(val);
      const el  = document.getElementById(rule.id);
      if (el) {
        el.classList.toggle("met", met);
        const check = el.querySelector(".check-path");
        const dot   = el.querySelector(".dot");
        if (check) check.setAttribute("opacity", met ? "1" : "0");
        if (dot)   dot.setAttribute("opacity",   met ? "0" : "1");
      }
      if (met) score++;
    });

    bars.forEach(b => { if (b) b.className = "strength-bar"; });

    const barClass = score <= 1 ? "active-weak"
                   : score <= 2 ? "active-fair"
                   : score <= 3 ? "active-good"
                   : "active-strong";

    for (let i = 0; i < Math.min(score, 4); i++) {
      if (bars[i]) bars[i].classList.add(barClass);
    }
  });

  if (confirmInput) {
    confirmInput.addEventListener("input", () => {
      if (!confirmInput.value) {
        if (confirmHint) confirmHint.textContent = "";
        return;
      }
      const match = passwordInput.value === confirmInput.value;
      if (confirmHint) {
        confirmHint.textContent = match ? "Passwords match." : "Passwords do not match.";
        confirmHint.style.color = match ? "var(--accent)" : "var(--danger)";
      }
    });
  }
});