# -*- coding: utf-8 -*-
"""Query semantic frame — understand the question ONCE, then route.

The systemic problem (owner's precision-strike directive): the answer path was a
race of regex lanes, each RE-GUESSING the subject and the intent. Two whole
failure classes fell out of it:
  * WRONG SUBJECT — '물의 화학식은?' picked 화학식 (the longest noun) and returned
    화학식's definition, because subject extraction was 'content nouns, longest
    first' with NO grammar. 물 (the real subject) was even dropped for being 1
    character.
  * MISROUTE — '피자 만드는 법' / '사랑이 뭐라고 생각해?' got the definition of the
    head noun, because the definition lane fires on ANY known concept regardless
    of what is actually being ASKED.

The fix is one structural parse, not more guards. A QueryFrame reads the
question's Korean grammar ONCE and yields:
  * subject     — what the question is ABOUT (the genitive possessor, the topic)
  * relation    — 'X의 Y' makes Y the requested relation (attribute), not a subject
  * answer_type — definition | relation | procedure | opinion | preference |
                  entity | greeting | smalltalk | realtime | unknown
  * conversational — whether this is talk, not lookup

Everything downstream reads the frame: subject extraction takes frame.subject
first (single-char included), the triple lookup uses frame.relation, and the
self-router uses frame.answer_type. No lane re-guesses.

Data-fused: the LEARNED router (trained, No-LLM) supplies the intent prior; the
grammatical parse supplies subject/relation and CORRECTS the router where the
router is weak. Deterministic, cheap, testable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# question words / frame markers that are never the subject
_QWORDS = {"뭐", "뭐야", "무엇", "무어", "누구", "언제", "어디", "어느", "어떤", "어떻게",
           "왜", "몇", "얼마", "무슨", "가장", "정말", "진짜"}
# bound nouns (의존명사) — grammatically never a standalone subject
_BOUND_NOUNS = {"게", "것", "건", "거", "수", "줄", "바", "때", "데", "점", "적", "채", "만큼"}
_JOSA_TAIL = re.compile(r"(은|는|이|가|을|를|의|에|에서|으로|로|와|과|도|만|이란|란|이라는|라는)$")

# relation surface -> the graph predicate family it asks for (used as intent).
# NOT a topic table — these are RELATION words (attributes), bounded and generic.
_RELATION_WORDS = {
    "수도": "capital", "화학식": "화학식", "저자": "author", "설립자": "설립자",
    "창시자": "설립자", "인구": "인구", "면적": "면적", "위치": "위치",
    "대통령": "국가원수", "총리": "정부수반", "ceo": "최고경영자", "대표": "최고경영자",
    "감독": "감독", "작가": "author", "발명자": "발명자", "발견자": "발견자",
    "국가": "country", "나라": "country", "종류": "is_a", "일종": "is_a",
    "뜻": "defined_as", "의미": "defined_as", "정의": "defined_as",
}

# procedure frame — asks HOW to do, not what a thing IS
_PROCEDURE = re.compile(r"(만드는\s*법|하는\s*법|끓이는\s*법|굽는\s*법|짓는\s*법"
                        r"|어떻게\s*(만들|해|하는지|하면|끓|굽)|레시피|방법\s*(알려|좀|이\s*뭐))")

# opinion / preference / feeling / small-talk — conversation, not lookup
# opinion frame: explicit '어떻게/뭐라고 생각' OR a value-judgment ('가장 중요한
# 게 뭐야' — asks for a JUDGMENT, not a lookup). Both are the opinion category.
_OPINION = re.compile(r"(어떻게\s*생각|뭐라고?\s*생각|무슨\s*생각|네\s*생각|너\s*생각"
                      r"|의견\s*(이|은)|어떻게\s*봐|어떤\s*것?\s*같아"
                      r"|(중요|소중|값진|의미|필요|가치)[가-힣]*\s*(게|것|건|점)\s*(뭐|무엇|어떤|어느|일까|인가))")
_PREFERENCE = re.compile(r"(좋아|싫어|선호|즐기)(해|하니|하세요|하나요|합니까|하시나요)\s*\??\s*$")
_FEELING = re.compile(r"(기분|컨디션|느낌)\s*(어때|어떠|좋아|괜찮)|힘들지|피곤하")
_SMALLTALK = re.compile(r"(심심|지루|재밌는\s*(얘기|이야기)|놀자|뭐\s*하고\s*놀|얘기\s*하자|말\s*걸)")
_ADVICE = re.compile(r"(어떻게\s*해야\s*(할까|하지|될까|좋을까)|조언\s*(좀|해)|어쩌면\s*좋)")
_GREETING = re.compile(r"(^|\s)(안녕|하이|헬로|반가|반갑|ㅎㅇ|잘\s*지내|좋은\s*(아침|저녁))")
_REALTIME = re.compile(r"(지금|오늘|현재|내일|요즘)\s*.*(날씨|시세|주가|가격|시간)"
                       r"|(날씨|시세|주가)\s*(어때|얼마|어떻게)")


@dataclass
class QueryFrame:
    raw: str
    subject: str = ""
    relation: str | None = None
    answer_type: str = "unknown"
    conversational: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"subject": self.subject, "relation": self.relation,
                "answer_type": self.answer_type, "conversational": self.conversational}


def _clean(tok: str) -> str:
    return _JOSA_TAIL.sub("", tok.strip()).strip()


def _head_noun(span: str) -> str:
    """The last content noun of a span, particle stripped, question-word skipped."""
    for tok in reversed(re.findall(r"[가-힣A-Za-z0-9]+", span)):
        base = _clean(tok)
        if base and base not in _QWORDS and base not in _BOUND_NOUNS and len(base) >= 1:
            return base
    return ""


def parse(question: str) -> QueryFrame:
    """One structural parse of the question. See module docstring."""
    q = str(question or "").strip()
    f = QueryFrame(raw=q)
    if not q:
        return f

    # 1) CONVERSATION frames win first — these are talk, not lookup.
    if _GREETING.search(q) and len(q) <= 24:
        f.answer_type, f.conversational = "greeting", True
        return f
    if _FEELING.search(q):
        f.answer_type, f.conversational = "feeling", True
        return f
    if _OPINION.search(q):
        f.answer_type, f.conversational = "opinion", True
        f.subject = _opinion_topic(q)
        return f
    if _PREFERENCE.search(q) or (re.search(r"(^|\s)(너|넌|너는|당신|네|니)\b", q)
                                 and re.search(r"(좋아|싫어|선호)", q)):
        f.answer_type, f.conversational = "preference", True
        f.subject = _opinion_topic(q)
        return f
    if _ADVICE.search(q):
        f.answer_type, f.conversational = "advice", True
        return f
    if _SMALLTALK.search(q):
        f.answer_type, f.conversational = "smalltalk", True
        return f
    if _REALTIME.search(q):
        f.answer_type = "realtime"
        return f

    # 2) PROCEDURE — how to DO, not what a thing IS.
    if _PROCEDURE.search(q):
        f.answer_type = "procedure"
        # the object of the procedure comes FIRST ('피자 맛있게 만드는 법' -> 피자,
        # 'X 끓이는 법' -> X); an adverb (맛있게/잘/빨리) can sit between object and
        # verb, so take the FIRST content noun, not the one adjacent to the verb.
        for tok in re.findall(r"[가-힣A-Za-z0-9]+", q):
            base = _clean(tok)
            if (base and base not in _QWORDS and base not in _BOUND_NOUNS
                    and not base.endswith(("게", "히", "이"))  # skip adverbs
                    and len(base) >= 2):
                f.subject = base
                break
        return f

    # 3) GENITIVE RELATION — 'X의 Y(는/가/이)?' : subject=X, relation=Y. THE fix for
    #    the wrong-subject class ('물의 화학식' -> subject 물, relation 화학식).
    m = re.search(r"([가-힣A-Za-z0-9 ]{1,30}?)\s*의\s+([가-힣A-Za-z0-9]{1,20})\s*(은|는|이|가)?\s*"
                  r"(뭐|무엇|누구|어디|어떻게|알려|말해)?", q)
    if m and "의" in q:
        subj = _clean(m.group(1))
        rel_word = _clean(m.group(2))
        if subj and rel_word and rel_word not in _QWORDS:
            f.subject = subj
            f.relation = _RELATION_WORDS.get(rel_word.lower(), rel_word)
            f.answer_type = "relation"
            return f

    # 4) TOPIC-RELATION without 의 — 'X는 Y가 뭐야' (rarer). Same subject=X, rel=Y.
    m = re.search(r"([가-힣A-Za-z0-9]{2,20})\s*(?:은|는)\s+([가-힣A-Za-z0-9]{1,20})\s*(?:이|가)\s*(?:뭐|무엇)", q)
    if m:
        subj, rel_word = _clean(m.group(1)), _clean(m.group(2))
        if subj and rel_word and rel_word not in _QWORDS:
            f.subject, f.relation, f.answer_type = subj, _RELATION_WORDS.get(rel_word.lower(), rel_word), "relation"
            return f

    # 5) ENTITY / DEFINITION — 'X는 누구야' (entity) / 'X란/뭐야' (definition).
    #    subject = the topic noun (genitive-free); single-char subjects allowed.
    if re.search(r"(누구|who)", q, re.I):
        f.answer_type = "entity"
    else:
        f.answer_type = "definition"
    f.subject = _definition_subject(q)
    return f


def _definition_subject(q: str) -> str:
    """Subject of an 'X는 뭐야 / X란' question: the topic before the copular frame."""
    # strip the trailing frame ('...는 뭐야', '...란', '...이 누구야')
    body = re.sub(r"\s*(은|는|이|가)?\s*(뭐야|뭐|무엇|누구|누구야|이란|란|이라는|라는|알려줘|설명해|뜻이?\s*뭐).*$",
                  "", q).strip()
    body = body or q
    return _head_noun(body)


def _opinion_topic(q: str) -> str:
    """Topic an opinion/preference question is ABOUT (사랑이 뭐라고 생각해 -> 사랑)."""
    body = re.sub(r"(에\s*대해서?|에\s*관해서?|이란|라는\s*게)?\s*"
                  r"(뭐라고?|무슨|어떻게|어떤)?\s*(생각|봐|같아|좋아|싫어|선호).*$", "", q).strip()
    head = _head_noun(body)
    return "" if head in _QWORDS or head in {"너", "당신", "네", "니"} else head
