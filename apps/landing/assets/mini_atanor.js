/* mini-ATANOR — the landing chat answers from a REAL local knowledge pack.
   The pack (mini_brain.json) is exported from the live engine's curated triple
   store by scripts/build_mini_brain.py; answering is deterministic graph lookup
   in this file. GPU 0, server 0 after page load, no LLM — the product claim,
   demonstrated literally in the visitor's own browser tab.
   Rebuild the pack + redeploy whenever the engine's knowledge grows. */
(function () {
  "use strict";

  var josa = function (w, a, b) {
    var c = w.charCodeAt(w.length - 1);
    return c >= 0xac00 && c <= 0xd7a3 && (c - 0xac00) % 28 !== 0 ? a : b;
  };
  var norm = function (s) { return String(s || "").replace(/\s+/g, " ").trim(); };
  var stripJosa = function (w) { return w.replace(/(이란|이라는|란|라는|은|는|이|가|을|를)$/, ""); };

  function buildIndex(pack) {
    var names = {}, bySubj = {}, relByKo = {};
    Object.keys(pack.concepts || {}).forEach(function (label) {
      names[label.replace(/\s+/g, "")] = label;
    });
    (pack.triples || []).forEach(function (t) {
      var s = t[0];
      names[s.replace(/\s+/g, "")] = s;
      (bySubj[s] = bySubj[s] || []).push(t);
    });
    Object.keys(pack.rel_ko || {}).forEach(function (rel) {
      relByKo[pack.rel_ko[rel]] = rel;
    });
    pack._names = names; pack._bySubj = bySubj; pack._relByKo = relByKo;
    return pack;
  }

  function resolveEntity(pack, name) {
    var n = norm(name).replace(/\s+/g, "");
    if (pack._names[n]) return pack._names[n];
    var s = stripJosa(norm(name)).replace(/\s+/g, "");
    return pack._names[s] || null;
  }

  function renderFact(pack, s, t) {
    var rel = t[1], o = t[2];
    if (rel === "capital" || rel === "수도") return s + "의 수도는 " + o + "입니다.";
    if (rel === "인구") return s + "의 인구는 " + o + "명입니다.";
    if (rel === "면적") return s + "의 면적은 " + o + "입니다.";
    if (rel === "defined_as" || rel === "is_a")
      return s + josa(s, "은", "는") + " " + o + (/[.다]$/.test(o) ? "" : "입니다.");
    var relKo = (pack.rel_ko || {})[rel] || rel;
    return s + "의 " + relKo + josa(relKo, "은", "는") + " " + o + "입니다.";
  }

  function answer(pack, qRaw) {
    var t0 = performance.now();
    var q = norm(qRaw).replace(/[?？!.…]+$/, "");
    if (!q) return null;
    var m = q.match(/^(.+?)의\s*(.+)$/);
    if (m) {
      var subj = resolveEntity(pack, m[1]);
      var relWord = stripJosa(norm(m[2]
        .replace(/(는|은|이|가)?\s*(뭐야|뭔가요|무엇인가요|무엇이야|무엇|얼마야|얼마|얼마나 돼|어디야|어디|알려줘|궁금해)?$/, "")));
      if (subj && relWord) {
        var rel = pack._relByKo[relWord] || relWord;
        var rows = pack._bySubj[subj] || [];
        for (var i = 0; i < rows.length; i++) {
          var t = rows[i];
          if (t[1] === rel || ((pack.rel_ko || {})[t[1]] || t[1]) === relWord) {
            return { text: renderFact(pack, subj, t), ms: performance.now() - t0, grounded: true };
          }
        }
      }
    }
    m = q.match(/^(.+?)(?:이|가|은|는)?\s*(?:뭐야|뭔가요|무엇인가요|무엇이야|무엇|누구야|누구|란|이란|알려줘|설명해줘)?$/);
    if (m) {
      var subj2 = resolveEntity(pack, m[1]);
      if (subj2) {
        var desc = (pack.concepts || {})[subj2];
        if (desc) {
          return { text: subj2 + josa(subj2, "은", "는") + " " + desc + (/[.다]$/.test(desc) ? "" : "입니다."),
                   ms: performance.now() - t0, grounded: true };
        }
        var rows2 = pack._bySubj[subj2] || [];
        for (var j = 0; j < rows2.length; j++) {
          if (rows2[j][1] === "defined_as" || rows2[j][1] === "is_a") {
            return { text: renderFact(pack, subj2, rows2[j]), ms: performance.now() - t0, grounded: true };
          }
        }
      }
    }
    return {
      text: "이 축소판 팩(" + ((pack.counts || {}).triples || 0) + "개 검증 사실)에는 그 근거가 없어 추측하지 않습니다 — 전체 ATANOR는 웹 검증과 학습 대기열로 이어서 답합니다.",
      ms: performance.now() - t0, grounded: false,
    };
  }

  // ---- UI wiring: turn the mock chat card into the live mini engine ----
  function initUI(pack) {
    var card = document.querySelector(".chatcard");
    if (!card) return;
    var form = document.createElement("form");
    form.className = "mini-ask";
    form.innerHTML =
      '<input type="text" autocomplete="off" ' +
      'placeholder="직접 물어보세요 — 이 브라우저 안에서 답합니다 (GPU 0 · 서버 0)" aria-label="mini atanor input"/>' +
      "<button type=\"submit\" aria-label=\"ask\">↑</button>";
    card.appendChild(form);
    var input = form.querySelector("input");
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var q = norm(input.value);
      if (!q) return;
      input.value = "";
      var u = document.createElement("div");
      u.className = "chatrow user";
      u.textContent = q;
      card.insertBefore(u, form);
      var r = answer(pack, q);
      var b = document.createElement("div");
      b.className = "chatrow bot";
      var span = document.createElement("span");
      span.textContent = r.text;
      b.appendChild(span);
      var cert = document.createElement("div");
      cert.className = "cert";
      cert.innerHTML = "<i></i><span></span>";
      cert.querySelector("span").textContent = r.grounded
        ? "미니 지식팩 조회 " + r.ms.toFixed(2) + " ms · GPU 0 · 서버 호출 0"
        : "정직한 보류 · 판정 " + r.ms.toFixed(2) + " ms";
      b.appendChild(cert);
      card.insertBefore(b, form);
      card.scrollTop = card.scrollHeight;
      if (window.__atanorOrbPulse) window.__atanorOrbPulse(r.grounded ? 1.0 : 0.45);
    });
  }

  fetch("assets/mini_brain.json")
    .then(function (r) { return r.json(); })
    .then(function (pack) { initUI(buildIndex(pack)); })
    .catch(function () { /* pack missing: the static mock stays as-is */ });

  // expose for tests
  window.MiniAtanor = { buildIndex: buildIndex, answer: answer };
})();
