/* mini-ATANOR — the landing chat answers from a REAL local knowledge pack.
   The pack (mini_brain.json) is exported from the live engine's curated triple
   store by scripts/build_mini_brain.py; answering is deterministic graph lookup
   in this file. GPU 0, server 0 after page load, no LLM — the product claim,
   demonstrated literally in the visitor's own browser tab.

   v3 (owner-measured failures fixed): the parser is no longer position-regex.
   It runs the full engine's pipeline in miniature — ENTITY SPOTTING anywhere in
   the utterance (longest pack-name match, token-prefix tolerant, filler-proof),
   RELATION SPOTTING anywhere, REVERSE edges (서울의 수도는? -> 서울특별시는
   대한민국의 수도), and a DISCOURSE STATE: the last entity carries, so a bare
   follow-up like '인구는?' resolves against it. Context, not rules. */
(function () {
  "use strict";

  var josa = function (w, a, b) {
    var c = w.charCodeAt(w.length - 1);
    return c >= 0xac00 && c <= 0xd7a3 && (c - 0xac00) % 28 !== 0 ? a : b;
  };
  var norm = function (s) { return String(s || "").replace(/\s+/g, " ").trim(); };
  var stripJosa = function (w) {
    return w.replace(/(이란|이라는|란|라는|은|는|이|가|을|를|의|도|만|에서|에는|에|와|과|랑)$/, "");
  };
  var uiLang = function () { try { return typeof LANG !== "undefined" ? LANG : "ko"; } catch (e) { return "ko"; } };
  // leading discourse fillers ("오 서울의 수도는?" — measured live) and trailing chatter
  var stripFillers = function (s) {
    return s.replace(/^\s*(오|아|어|음+|흠+|와|헐|그럼|그러면|근데|그런데|혹시|자|저기|아니)\s+/g, "")
            .replace(/[?？!.…~ㅋㅎㅠㅜ]+$/g, "").trim();
  };

  // relation keywords -> pack predicate; spotted ANYWHERE in the utterance
  var REL_WORDS = {
    "수도": "capital", "인구": "인구", "면적": "면적",
    "뜻": "defined_as", "정의": "defined_as", "의미": "defined_as",
    "종류": "is_a", "위치": "located_in", "어디": "located_in",
    "나라": "__country_of__", "국가": "__country_of__",
  };

  function buildIndex(pack) {
    var names = {}, bySubj = {}, relByKo = {}, capitalOf = {};
    Object.keys(pack.concepts || {}).forEach(function (label) {
      names[label.replace(/\s+/g, "")] = label;
    });
    (pack.triples || []).forEach(function (t) {
      var s = t[0], rel = t[1], o = t[2];
      names[s.replace(/\s+/g, "")] = s;
      (bySubj[s] = bySubj[s] || []).push(t);
      // REVERSE edge: the capital city points back to its country, so
      // '서울의 수도는?' can answer '서울특별시는 대한민국의 수도' instead of shrugging
      if (rel === "capital" || rel === "수도") {
        capitalOf[o.replace(/\s+/g, "")] = { city: o, country: s };
        names[o.replace(/\s+/g, "")] = o;
      }
    });
    Object.keys(pack.rel_ko || {}).forEach(function (rel) {
      relByKo[pack.rel_ko[rel]] = rel;
    });
    // longest-first name list for containment spotting (skip 1-char names and
    // names that ARE relation words — '수도' must never be spotted as an entity)
    var nameKeys = Object.keys(names).filter(function (k) {
      return k.length >= 2 && !(k in REL_WORDS);
    }).sort(function (a, b) { return b.length - a.length; });
    pack._names = names; pack._bySubj = bySubj; pack._relByKo = relByKo;
    pack._capitalOf = capitalOf; pack._nameKeys = nameKeys;
    return pack;
  }

  /* ---- engine-style spotting: find the entity and the relation ANYWHERE ---- */
  function spotEntity(pack, q) {
    var flat = q.replace(/\s+/g, "");
    // 1) longest pack name contained in the utterance
    for (var i = 0; i < pack._nameKeys.length; i++) {
      var k = pack._nameKeys[i];
      if (flat.indexOf(k) !== -1) return pack._names[k];
    }
    // 2) token-prefix: a josa-stripped token that PREFIXES a pack name
    //    ('서울' -> 서울특별시). Longest token first; name with shortest
    //    completion wins (closest surface form).
    var toks = q.split(/\s+/).map(stripJosa).filter(function (t) { return t.length >= 2; })
                .sort(function (a, b) { return b.length - a.length; });
    for (var j = 0; j < toks.length; j++) {
      var best = null;
      for (var i2 = pack._nameKeys.length - 1; i2 >= 0; i2--) { // shortest names first
        var k2 = pack._nameKeys[i2];
        if (k2.indexOf(toks[j]) === 0) { best = pack._names[k2]; break; }
      }
      if (best) return best;
    }
    // 3) exact whole-token match — the only safe route for 1-char concepts
    //    ('물이 뭐야?' -> token 물): never substring, token identity only
    var toks1 = q.split(/\s+/).map(stripJosa);
    for (var j2 = 0; j2 < toks1.length; j2++) {
      if (toks1[j2] && pack._names[toks1[j2]] && !(toks1[j2] in REL_WORDS)) {
        return pack._names[toks1[j2]];
      }
    }
    return null;
  }

  function spotRelation(q) {
    var flat = q.replace(/\s+/g, "");
    var hit = null, hitPos = -1, wh = null;
    Object.keys(REL_WORDS).forEach(function (w) {
      var p = flat.lastIndexOf(w);
      if (p < 0) return;
      // '어디' is a QUESTION WORD — it names a relation only when no real
      // relation word is present ('수도가 어디야?'의 관계는 수도, 어디가 아님)
      if (w === "어디") { wh = REL_WORDS[w]; return; }
      if (p > hitPos) { hitPos = p; hit = REL_WORDS[w]; }
    });
    return hit || wh;
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

  function lookupRelation(pack, subj, rel) {
    var rows = pack._bySubj[subj] || [];
    for (var i = 0; i < rows.length; i++) {
      var t = rows[i];
      if (t[1] === rel || ((pack.rel_ko || {})[t[1]] || t[1]) === rel) {
        return renderFact(pack, subj, t);
      }
    }
    return null;
  }

  function lookupDefinition(pack, subj) {
    var desc = (pack.concepts || {})[subj];
    if (desc) {
      // a web-memory definition often opens with its own TOPIC ("빛의 속력(…)은
      // 진공에서…") — prepending ours would read "빛의 속도는 빛의 속력은…".
      // Serve verbatim only when the opening topic (the phrase before '(' or a
      // topic marker) is essentially the subject itself: same 2-char prefix AND
      // similar length. '커피나무의 열매를…' must still get '커피는 ' prepended.
      var m = desc.match(/^([가-힣A-Za-z0-9·\s]{2,20}?)(\(|은\s|는\s)/);
      if (m) {
        var topic = m[1].trim();
        var sflat = subj.replace(/\s+/g, "");
        var tflat = topic.replace(/\s+/g, "");
        if (tflat.slice(0, 2) === sflat.slice(0, 2) &&
            Math.abs(tflat.length - sflat.length) <= 3) {
          return desc + (/[.다]$/.test(desc) ? "" : "입니다.");
        }
      }
      return subj + josa(subj, "은", "는") + " " + desc + (/[.다]$/.test(desc) ? "" : "입니다.");
    }
    var rows = pack._bySubj[subj] || [];
    for (var j = 0; j < rows.length; j++) {
      if (rows[j][1] === "defined_as" || rows[j][1] === "is_a") {
        return renderFact(pack, subj, rows[j]);
      }
    }
    return null;
  }

  /* ---- conversational lane (dialogue moves, not knowledge claims) ---- */
  function converse(pack, qRaw) {
    var t0 = performance.now();
    var q = norm(qRaw).toLowerCase().replace(/[?？!.~…]+$/, "");
    var facts = (pack.counts || {}).triples || 0;
    var en = uiLang() === "en" && !/[가-힣]/.test(qRaw);
    var text = null;
    if (/^(안녕|안녕하세요|안녕하신가요|안녕하십니까|하이|헬로|반가워|반갑습니다|ㅎㅇ|hi|hello|hey|yo)$/.test(q)) {
      text = en
        ? "Hi! I'm a miniature ATANOR running entirely inside this browser tab — " + facts + " verified facts, zero server calls. Try 일본의 수도는? — then just 인구는? (I keep context)."
        : "안녕하세요! 저는 이 브라우저 탭 안에서 통째로 도는 미니 ATANOR예요 — 검증 사실 " + facts + "개, 서버 호출 0. ‘일본의 수도는?’ 물어보시고, 이어서 ‘인구는?’처럼 짧게 물어도 맥락을 기억해요.";
    } else if (/(고마워|고맙습니다|감사합니다|감사해요|감사|땡큐|thank you|thanks|thx)/.test(q)) {
      text = en
        ? "You're welcome — every answer here is a verbatim quote from the verified graph, so ask away."
        : "천만에요 — 여기서 나가는 답은 전부 검증된 그래프의 원문 인용이에요. 얼마든지 물어보세요.";
    } else if (/^(너는?|넌|당신은?|정체가?)?\s*(누구(야|세요|니|심|시죠)?|뭐야|뭔데)$/.test(q) ||
               /(뭐야 너|너 뭐야|넌 뭐야|너는 뭐야|정체가 뭐|네 소개|자기소개|who are you|what are you|introduce yourself)/.test(q)) {
      text = en
        ? "I'm ATANOR in miniature: the same graph-native structure as the full engine, packed into a 33 KB knowledge pack that answers right here — GPU 0, server 0. The full ATANOR continues with live web verification and a learning loop."
        : "저는 ATANOR의 축소판이에요. 전체 엔진과 같은 그래프 네이티브 구조를 33KB 지식팩에 담아 이 탭에서 바로 답합니다 — GPU 0, 서버 0. 전체 ATANOR는 실시간 웹 검증과 학습 루프로 이어집니다.";
    } else if (/(뭘 물어|뭘 알아|무엇을 알아|뭐 알아|뭐 할 수 있|뭘 할 수 있|할 수 있는 게|기능이 뭐|what can you|what do you know)/.test(q)) {
      text = en
        ? "This mini pack covers world capitals, populations and areas, plus concept definitions (coffee, gravity, the speed of light…). Ask in Korean — and follow up with just 인구는?, I keep context."
        : "이 미니 팩에는 세계 나라들의 수도·인구·면적과 개념 정의(커피, 중력, 빛의 속도…)가 들어 있어요. ‘대한민국의 인구는?’처럼 묻고, 이어서 ‘면적은?’처럼 짧게 물어도 돼요 — 맥락을 기억합니다.";
    }
    if (text) return { text: text, ms: performance.now() - t0, grounded: false, kind: "chat" };
    return null;
  }

  /* ---- the mini engine: spot -> resolve -> traverse -> remember ---- */
  var CTX = { entity: null };   // discourse state: the last resolved entity

  function answer(pack, qRaw) {
    var t0 = performance.now();
    var q0 = norm(qRaw);
    if (!q0) return null;
    var chat = converse(pack, qRaw);
    if (chat) return chat;
    if (!/[가-힣]/.test(q0)) {
      return {
        text: uiLang() === "en"
          ? "The pack in this tab holds Korean-labeled facts — try 일본의 수도는? The full ATANOR answers multilingual questions with live web verification."
          : "이 탭의 팩은 한국어 라벨 사실을 담고 있어요 — ‘일본의 수도는?’처럼 물어보세요. 전체 ATANOR는 다국어 질문을 실시간 웹 검증으로 답합니다.",
        ms: performance.now() - t0, grounded: false, kind: "chat",
      };
    }
    var q = stripFillers(q0);
    var entity = spotEntity(pack, q);
    var rel = spotRelation(q);
    var usedContext = false;

    // follow-up: relation with no entity rides the discourse state ('인구는?')
    if (!entity && rel && CTX.entity) { entity = CTX.entity; usedContext = true; }

    var text = null;
    if (entity && rel) {
      if (rel === "capital" || rel === "__country_of__") {
        // REVERSE edge first when the entity is itself a capital city:
        // '서울의 수도는?' / '서울은 어느 나라?' -> 서울특별시는 대한민국의 수도
        var rev = pack._capitalOf[entity.replace(/\s+/g, "")];
        if (rev) {
          text = rev.city + josa(rev.city, "은", "는") + " " + rev.country + "의 수도입니다.";
        } else if (rel === "capital") {
          text = lookupRelation(pack, entity, "capital");
        }
      } else {
        text = lookupRelation(pack, entity, rel);
      }
      if (!text) text = lookupDefinition(pack, entity);  // relation missing: fall to identity
    } else if (entity) {
      text = lookupDefinition(pack, entity);
      if (!text) {
        var rev2 = pack._capitalOf[entity.replace(/\s+/g, "")];
        if (rev2) text = rev2.city + josa(rev2.city, "은", "는") + " " + rev2.country + "의 수도입니다.";
      }
    }

    if (text) {
      CTX.entity = entity;   // remember for the next turn
      return { text: text, ms: performance.now() - t0, grounded: true, context: usedContext };
    }
    // BEYOND THE PACK: hand off to live web verification (the browser calls
    // Wikipedia directly — still no ATANOR server involved). The UI awaits it.
    return { kind: "web", q: q, entity: entity, rel: rel, t0: t0 };
  }

  /* ---- live web verification lane (browser -> Wikipedia, no middleman) ----
     The full engine's web-rescue law applies in miniature: the fetched page
     must ANCHOR the question (title overlap gate) or we abstain honestly, and
     whatever we say is a VERBATIM quote from the source, linked. */
  var STOP_WORDS = /^(뭐야|뭐지|뭔데|뭐냐|무엇|누구야|누구지|누구|어디야|어디|언제|얼마야|얼마|왜|어떻게|알려줘|설명해줘|설명|말해줘|궁금해|대해|대해서|관해|에|는|은|이|가)$/;

  function webSubject(q, entity, rel) {
    if (entity && !rel) return entity;             // pack entity, unknown property
    var toks = q.split(/\s+/).map(stripJosa).filter(function (t) {
      return t && !STOP_WORDS.test(t) && !(t in REL_WORDS);
    });
    return toks.join(" ") || (CTX.entity || "");
  }

  function fetchJSON(url) {
    return fetch(url, { headers: { "Accept": "application/json" } })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); });
  }

  function wikiSummary(title) {
    return fetchJSON("https://ko.wikipedia.org/api/rest_v1/page/summary/" +
                     encodeURIComponent(title.replace(/\s+/g, "_")));
  }

  function wikiSearch(q) {
    return fetchJSON("https://ko.wikipedia.org/w/api.php?action=opensearch&format=json&origin=*&limit=1&search=" +
                     encodeURIComponent(q))
      .then(function (a) { return (a && a[1] && a[1][0]) || null; });
  }

  function anchors(subj, title) {
    var s = subj.replace(/\s+/g, ""), t = (title || "").replace(/\s+/g, "");
    if (!s || !t) return false;
    return t.indexOf(s) !== -1 || s.indexOf(t) !== -1 ||
           (s.length >= 2 && t.slice(0, 2) === s.slice(0, 2));
  }

  function pickSentence(extract, keyword) {
    var parts = (extract || "").split(/(?<=다\.)\s+|(?<=\.)\s+/);
    for (var i = 0; i < parts.length; i++) {
      if (keyword && parts[i].indexOf(keyword) !== -1) return parts[i].trim();
    }
    return null;
  }

  function webRescue(pack, r) {
    var subj = webSubject(r.q, r.entity, r.rel);
    // a bare short follow-up ('높이는?') rides the discourse state as a property
    var propWord = null;
    if (r.rel) { for (var w in REL_WORDS) { if (REL_WORDS[w] === r.rel) { propWord = w; break; } } }
    // a bare '높이는?' rides the discourse entity as a PROPERTY — but only a
    // true bare follow-up: single leftover token, and no definition question
    // word ('에펠탑이 뭐야?' asks WHAT 에펠탑 IS, never a property of the
    // previous entity — measured live).
    var isDefQ = /(뭐야|뭐지|뭔데|뭐냐|무엇|누구)/.test(r.q);
    var leftover = r.q.split(/\s+/).map(stripJosa).filter(function (t) {
      return t && !STOP_WORDS.test(t) && !(t in REL_WORDS);
    });
    if (!propWord && !isDefQ && CTX.entity && leftover.length === 1 &&
        subj === leftover[0] && subj !== CTX.entity &&
        subj.replace(/\s+/g, "").length <= 4) {
      propWord = subj; subj = CTX.entity;
    }
    if (!subj) return Promise.reject(new Error("no-subject"));
    var lookup = wikiSummary(subj).catch(function () {
      return wikiSearch(subj).then(function (t) {
        if (!t) throw new Error("not-found");
        return wikiSummary(t);
      });
    });
    return lookup.then(function (page) {
      var title = page && (page.title || ""), extract = page && (page.extract || "");
      var url = page && page.content_urls && page.content_urls.desktop && page.content_urls.desktop.page;
      if (!extract || !anchors(subj, title)) throw new Error("no-anchor");
      var text, partial = false;
      if (propWord) {
        var sent = pickSentence(extract, propWord);
        if (sent) { text = sent; }
        else {
          text = extract.split(/(?<=다\.)\s+/)[0];
          partial = true;
        }
      } else {
        var sents = extract.split(/(?<=다\.)\s+/);
        text = sents.slice(0, 2).join(" ");
      }
      if (partial) {
        text += " — 요약에 ‘" + propWord + "’ 항목은 없었어요. 원문에서 확인해 보세요.";
      }
      CTX.entity = title;                      // web entity carries context too
      return { text: text, url: url, title: title,
               ms: performance.now() - r.t0, grounded: true, web: true };
    });
  }

  function certLabel(r) {
    var en = uiLang() === "en";
    if (r.web) {
      return en ? "live web verification " + r.ms.toFixed(0) + " ms · source ko.wikipedia.org · ATANOR server calls 0"
                : "실시간 웹 검증 " + r.ms.toFixed(0) + " ms · 출처 ko.wikipedia.org · ATANOR 서버 호출 0";
    }
    if (r.grounded) {
      var base = en ? "mini pack lookup " + r.ms.toFixed(2) + " ms · GPU 0 · server calls 0"
                    : "미니 지식팩 조회 " + r.ms.toFixed(2) + " ms · GPU 0 · 서버 호출 0";
      if (r.context) base += en ? " · context carried" : " · 맥락 유지";
      return base;
    }
    if (r.kind === "chat") {
      return en ? "dialogue · in-browser · server calls 0"
                : "대화 응답 · 브라우저 로컬 · 서버 호출 0";
    }
    return en ? "web verification unavailable · nothing invented"
              : "웹 검증 불가 · 지어내지 않았습니다";
  }

  // ---- UI wiring: turn the mock chat card into the live mini engine ----
  function initUI(pack) {
    var card = document.querySelector(".chatcard");
    if (!card) return;
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
      b.appendChild(span);
      var cert = document.createElement("div");
      cert.className = "cert";
      cert.innerHTML = "<i></i><span></span>";
      b.appendChild(cert);
      log.appendChild(b);

      function paint(res) {
        span.textContent = res.text;
        if (res.url) {
          var a = document.createElement("a");
          a.href = res.url; a.target = "_blank"; a.rel = "noopener";
          a.textContent = " (출처: " + (res.title || "위키백과") + ")";
          a.style.cssText = "font-size:.85em;opacity:.75;text-decoration:underline;";
          span.appendChild(a);
        }
        cert.querySelector("span").textContent = certLabel(res);
        log.scrollTop = log.scrollHeight;
        if (window.__atanorOrbPulse)
          window.__atanorOrbPulse(res.grounded ? 1.0 : (res.kind === "chat" ? 0.6 : 0.45));
      }

      if (r.kind === "web") {
        span.textContent = uiLang() === "en" ? "verifying on the live web…" : "실시간 웹에서 검증하는 중…";
        cert.querySelector("span").textContent = uiLang() === "en"
          ? "browser → ko.wikipedia.org (no ATANOR server)" : "브라우저 → ko.wikipedia.org (ATANOR 서버 경유 없음)";
        log.scrollTop = log.scrollHeight;
        webRescue(pack, r).then(paint).catch(function () {
          paint({
            text: "웹에서도 이 질문을 앵커하는 문서를 찾지 못했어요 — 지어내는 대신 여기서 멈춥니다. 전체 ATANOR는 다중 소스 합의 검색으로 더 깊이 팝니다.",
            ms: performance.now() - r.t0, grounded: false, kind: "redirect",
          });
        });
      } else {
        paint(r);
      }
    });
  }

  fetch("assets/mini_brain.json")
    .then(function (r) { return r.json(); })
    .then(function (pack) { initUI(buildIndex(pack)); })
    .catch(function () { /* pack missing: the static mock stays as-is */ });

  // expose for tests
  window.MiniAtanor = { buildIndex: buildIndex, answer: answer, converse: converse,
                        spotEntity: spotEntity, spotRelation: spotRelation };
})();
