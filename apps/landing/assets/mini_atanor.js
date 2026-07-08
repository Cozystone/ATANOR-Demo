/* mini-ATANOR — the landing chat answers from a REAL local knowledge pack.
   The pack (mini_brain.json) is exported from the live engine's curated triple
   store by scripts/build_mini_brain.py; answering is deterministic graph lookup
   in this file. GPU 0, server 0 after page load, no LLM — the product claim,
   demonstrated literally in the visitor's own browser tab.
   Rebuilt automatically on every answer-pack promotion tick; redeploy ships it. */
(function () {
  "use strict";

  var josa = function (w, a, b) {
    var c = w.charCodeAt(w.length - 1);
    return c >= 0xac00 && c <= 0xd7a3 && (c - 0xac00) % 28 !== 0 ? a : b;
  };
  var norm = function (s) { return String(s || "").replace(/\s+/g, " ").trim(); };
  var stripJosa = function (w) { return w.replace(/(이란|이라는|란|라는|은|는|이|가|을|를)$/, ""); };
  var uiLang = function () { try { return typeof LANG !== "undefined" ? LANG : "ko"; } catch (e) { return "ko"; } };

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

  /* ---- conversational lane: the mini meets greetings and meta questions
     head-on instead of routing them to the fact lookup. These are dialogue
     moves, not knowledge claims — nothing here asserts a fact. ---- */
  function converse(pack, qRaw) {
    var t0 = performance.now();
    var q = norm(qRaw).toLowerCase().replace(/[?？!.~…]+$/, "");
    var facts = (pack.counts || {}).triples || 0;
    // reply in the asker's language: Hangul input gets Korean even on the EN page
    var en = uiLang() === "en" && !/[가-힣]/.test(qRaw);
    var text = null;
    if (/^(안녕|안녕하세요|안녕하신가요|안녕하십니까|하이|헬로|반가워|반갑습니다|ㅎㅇ|hi|hello|hey|yo)$/.test(q)) {
      text = en
        ? "Hi! I'm a miniature ATANOR running entirely inside this browser tab — " + facts + " verified facts, zero server calls. Try 일본의 수도는? or 커피가 뭐야?"
        : "안녕하세요! 저는 이 브라우저 탭 안에서 통째로 도는 미니 ATANOR예요 — 검증 사실 " + facts + "개, 서버 호출 0. ‘일본의 수도는?’, ‘커피가 뭐야?’처럼 물어보세요.";
    } else if (/(고마워|고맙습니다|감사합니다|감사해요|감사|땡큐|thank you|thanks|thx)/.test(q)) {
      text = en
        ? "You're welcome — every answer here is a verbatim quote from the verified graph, so ask away."
        : "천만에요 — 여기서 나가는 답은 전부 검증된 그래프의 원문 인용이에요. 얼마든지 물어보세요.";
    } else if (/(누구야|누구세요|누구니|뭐야 너|너 뭐야|넌 뭐야|너는 뭐야|정체가 뭐|네 소개|자기소개|who are you|what are you|introduce yourself)/.test(q)) {
      text = en
        ? "I'm ATANOR in miniature: the same graph-native structure as the full engine, packed into a 33 KB knowledge pack that answers right here — GPU 0, server 0. The full ATANOR continues with live web verification and a learning loop."
        : "저는 ATANOR의 축소판이에요. 전체 엔진과 같은 그래프 네이티브 구조를 33KB 지식팩에 담아 이 탭에서 바로 답합니다 — GPU 0, 서버 0. 전체 ATANOR는 실시간 웹 검증과 학습 루프로 이어집니다.";
    } else if (/(뭘 물어|뭘 알아|무엇을 알아|뭐 알아|뭐 할 수 있|뭘 할 수 있|할 수 있는 게|기능이 뭐|what can you|what do you know)/.test(q)) {
      text = en
        ? "This mini pack covers world capitals, populations and areas, plus concept definitions (coffee, gravity, the speed of light…). Ask in Korean — e.g. 대한민국의 인구는? The full ATANOR goes far beyond the pack with live web verification."
        : "이 미니 팩에는 세계 나라들의 수도·인구·면적과 개념 정의(커피, 중력, 빛의 속도…)가 들어 있어요. ‘대한민국의 인구는?’처럼 물어보세요. 전체 ATANOR는 실시간 웹 검증으로 팩 너머까지 답합니다.";
    }
    if (text) return { text: text, ms: performance.now() - t0, grounded: false, kind: "chat" };
    return null;
  }

  function answer(pack, qRaw) {
    var t0 = performance.now();
    var q = norm(qRaw).replace(/[?？!.…]+$/, "");
    if (!q) return null;
    var chat = converse(pack, qRaw);
    if (chat) return chat;
    // the pack's labels are Korean; meet English input with a guide, not a shrug
    if (!/[가-힣]/.test(q)) {
      return {
        text: uiLang() === "en"
          ? "The pack in this tab holds Korean-labeled facts — try 일본의 수도는? or 커피가 뭐야? The full ATANOR answers multilingual questions with live web verification."
          : "이 탭의 팩은 한국어 라벨 사실을 담고 있어요 — ‘일본의 수도는?’처럼 물어보세요. 전체 ATANOR는 다국어 질문을 실시간 웹 검증으로 답합니다.",
        ms: performance.now() - t0, grounded: false, kind: "chat",
      };
    }
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
    // "일본 수도", "대한민국 인구" — the genitive marker is often dropped in speech
    m = q.match(/^(.+?)[\s,]+(수도|인구|면적)[은는이가]?\s*(?:뭐야|어디야|얼마야|얼마)?$/);
    if (m) {
      var subjB = resolveEntity(pack, m[1]);
      if (subjB) {
        var relB = pack._relByKo[m[2]] || m[2];
        var rowsB = pack._bySubj[subjB] || [];
        for (var b = 0; b < rowsB.length; b++) {
          if (rowsB[b][1] === relB || ((pack.rel_ko || {})[rowsB[b][1]] || rowsB[b][1]) === m[2]) {
            return { text: renderFact(pack, subjB, rowsB[b]), ms: performance.now() - t0, grounded: true };
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
    // outside the pack: point forward to what works, and to the full engine —
    // the mini's scope is the pack; the architecture's answer is the learn loop
    return {
      text: uiLang() === "en"
        ? "That one lives beyond this tab's " + (((pack.counts || {}).triples) || 0) + "-fact mini pack — the full ATANOR takes it from here with live web verification, and what it learns joins the graph. In this tab, try 일본의 수도는? or 중력이 뭐야?"
        : "그 주제는 이 탭의 미니 팩(" + (((pack.counts || {}).triples) || 0) + "개 검증 사실) 너머에 있어요 — 전체 ATANOR는 여기서부터 실시간 웹 검증으로 이어 답하고, 배운 것은 그래프에 남습니다. 이 탭에서는 ‘일본의 수도는?’, ‘중력이 뭐야?’를 바로 답해요.",
      ms: performance.now() - t0, grounded: false, kind: "redirect",
    };
  }

  function certLabel(r) {
    var en = uiLang() === "en";
    if (r.grounded) {
      return en ? "mini pack lookup " + r.ms.toFixed(2) + " ms · GPU 0 · server calls 0"
                : "미니 지식팩 조회 " + r.ms.toFixed(2) + " ms · GPU 0 · 서버 호출 0";
    }
    if (r.kind === "chat") {
      return en ? "dialogue · in-browser · server calls 0"
                : "대화 응답 · 브라우저 로컬 · 서버 호출 0";
    }
    return en ? "beyond the mini pack · the full engine continues with web verification"
              : "미니 팩 너머 · 전체 엔진은 웹 검증으로 계속";
  }

  // ---- UI wiring: turn the mock chat card into the live mini engine ----
  function initUI(pack) {
    var card = document.querySelector(".chatcard");
    if (!card) return;
    // messages live in a scrollable log; the ask bar stays pinned at the bottom
    var log = document.createElement("div");
    log.className = "mini-log";
    while (card.firstChild) log.appendChild(card.firstChild);
    card.appendChild(log);
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
      log.appendChild(u);
      var r = answer(pack, q);
      var b = document.createElement("div");
      b.className = "chatrow bot";
      var span = document.createElement("span");
      span.textContent = r.text;
      b.appendChild(span);
      var cert = document.createElement("div");
      cert.className = "cert";
      cert.innerHTML = "<i></i><span></span>";
      cert.querySelector("span").textContent = certLabel(r);
      b.appendChild(cert);
      log.appendChild(b);
      log.scrollTop = log.scrollHeight;
      if (window.__atanorOrbPulse)
        window.__atanorOrbPulse(r.grounded ? 1.0 : (r.kind === "chat" ? 0.6 : 0.45));
    });
  }

  fetch("assets/mini_brain.json")
    .then(function (r) { return r.json(); })
    .then(function (pack) { initUI(buildIndex(pack)); })
    .catch(function () { /* pack missing: the static mock stays as-is */ });

  // expose for tests
  window.MiniAtanor = { buildIndex: buildIndex, answer: answer, converse: converse };
})();
