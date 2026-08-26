import json
import os
import re

import httpx
import yaml
from pydantic import ValidationError

from .schemas import PalmistryReport


FIXED_DISCLAIMER = "本卷轴由 AI 结合传统易理相学生成，仅供国学文化交流与雅玩，不作现代医学或人生决策之用。"
FORBIDDEN = ("疾病诊断", "寿命预测", "心脏病", "癌症", "抑郁症", "焦虑症", "一定会", "注定", "智商")
LINE_KEYS = ("foundation", "wisdom", "karma", "career", "marriage")


def load_rules() -> tuple[str, dict]:
    path = os.path.join(os.path.dirname(__file__), "rules", "palmistry_rules.yaml")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return str(data["version"]), data


def _endpoint(base_url: str) -> str:
    base = base_url.rstrip("/")
    return base + "/chat/completions" if base.endswith("/v1") else base + "/v1/chat/completions"


def _json_from_text(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I | re.S).strip()
    return json.loads(text)


def _text(value: object, fallback: str, limit: int = 1400) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()[:limit]
    if isinstance(value, dict):
        return "；".join(f"{k}：{v}" for k, v in value.items() if v)[:limit] or fallback
    return fallback


def _bounded_long_text(value: object, fallback: str) -> str:
    """Keep the model's wording intact; never manufacture filler text."""
    return _text(value, fallback, 150)


def _stage(raw: object, title: str, classical: str, modern: str) -> dict:
    item = raw if isinstance(raw, dict) else {}
    return {"title": _text(item.get("title"), title, 120), "classical": _bounded_long_text(item.get("classical"), classical), "modern": _bounded_long_text(item.get("modern"), modern)}


def _normalize_payload(raw: dict) -> dict:
    """Normalize the bilingual five-line report and tolerate the previous flat schema."""
    observations_raw = raw.get("observations") if isinstance(raw.get("observations"), dict) else {}
    aliases = {"earth": ("earth", "earth_line", "life_line"), "human": ("human", "human_line", "head_line"), "heaven": ("heaven", "heaven_line", "heart_line"), "jade": ("jade", "jade_pillar_line"), "family": ("family", "family_ethos_line")}
    observations = {}
    for key, names in aliases.items():
        value = next((observations_raw.get(name) for name in names if observations_raw.get(name)), None)
        observations[key] = _text(value, "纹理幽微，隐而不显，尚待更清晰的掌面影像以观其势。", 700)

    raw_analysis = raw.get("analysis") if isinstance(raw.get("analysis"), dict) else {}
    old = raw.get("traditional_interpretation") if isinstance(raw.get("traditional_interpretation"), dict) else {}
    classical_raw = raw_analysis.get("classical") if isinstance(raw_analysis.get("classical"), dict) else {}
    modern_raw = raw_analysis.get("modern") if isinstance(raw_analysis.get("modern"), dict) else {}
    old_map = {"foundation": old.get("health_energy") or old.get("生命线"), "wisdom": old.get("career_mind") or old.get("智慧线"), "karma": old.get("emotional_status") or old.get("感情线"), "career": old.get("career"), "marriage": old.get("marriage")}
    classical_defaults = {
        "foundation": "地纹盘桓而势稳，根基有本，气象宜藏锋蓄力；早年或多凭自持应对变化，中途虽有风雨，终能以耐性守住根脉。凡事先固其本、再图其远，顺应四时而不改初心，待时机成熟，自有厚土承载长行之路；以静制动，厚积而后发。",
        "wisdom": "人纹横展而略有下势，心思细密，善于权衡进退；所虑既深，亦易因求全而迟疑。此象贵在收敛杂念、专注一端，将所见所学化作次第可行之策。藏锋守拙而不失果断，谋定之后稳步推进，终能在纷繁处自开清明格局；以定见行，以行证心。",
        "karma": "天纹弧行而深浅相间，情志有源，待人重真诚而不轻许诺；缘分往往先经试探，后于相知中见其厚薄。宜守柔而有界，直抒所感，莫使未言之意积成心结。以宽厚待人、以清醒自守，情路自能由曲入平，得长久安宁；缘来不拒，缘去不执。",
        "career": "玉柱纹由掌底向上，纵势虽淡而根气未绝，事业之机多在积累与转折之间显现；不宜急逐虚名，宜先立一技、再借众力成局。行事守信，遇变能调，便可把暂时的隐而不显化为后来的基业开拓，于实处见社会成就；功在不舍，名由实立。",
        "marriage": "家风纹潜藏不露，姻缘之事重在相处日久、彼此扶持；情感并非骤然定局，而是在共同承担与互相体谅中渐次成形。宜以敬为先、以诚为要，给伴侣留有呼吸与成长的余地。家道贵和，守住日常温度，便能迎来成家立业之机；相扶相成，家声自远。",
    }
    modern_defaults = {
        "foundation": "从地纹的走势来看，你往往愿意先把生活安顿好，再腾出空间追求变化；压力大时容易独自扛住、忽略补充能量。把长期目标拆成今天能完成的小步，每周安排固定休息与复盘，也主动向可信的人求助，稳定节奏会让你更有余力成长。",
        "wisdom": "人纹的走向像是既重逻辑又保有想象力的人：你会反复比较细节，想把风险都想完，反而容易错过行动窗口。给每次选择设三项核心标准和明确截止时间，先用低成本的小实验验证，再根据反馈调整，不必等到百分之百确定才开始。",
        "karma": "天纹深浅交替，说明你在关系里重视情绪温度，却不总愿意及时说出脆弱和需要；沉默久了，体贴可能变成彼此猜测。练习用“我感到”和“我需要”表达当下，每周留一段不急着解决问题的对话时间，亲近与边界就能同时被照顾。",
        "career": "玉柱纹偏淡而仍有纵向根气，提醒你把职业看成持续校准的旅程，而非一次选择定终身。你可能在稳定与转向之间犹豫，真正的阻力是害怕投入后改变。保留现有底盘，同时用项目、课程或合作试水，让下一步建立在真实经验上，机会会更容易被接住。",
        "marriage": "家风纹不明显时，关系更需要靠日常行动而不是等待某个确定信号。你可能同时顾及家人期待、现实责任和个人感受，疲惫若不说就会变成摩擦。和伴侣约定固定的沟通时段，分别说出感受、需求与可承担的事，慢一点确认反而更踏实。",
    }
    analysis = {"classical": {}, "modern": {}}
    for key in LINE_KEYS:
        analysis["classical"][key] = _bounded_long_text(classical_raw.get(key) or old_map.get(key), classical_defaults[key])
        analysis["modern"][key] = _bounded_long_text(modern_raw.get(key) or old_map.get(key), modern_defaults[key])

    timeline_raw = raw.get("timeline") if isinstance(raw.get("timeline"), dict) else {}
    timeline = {
        "early_years": _stage(timeline_raw.get("early_years"), "早年启蒙：潜龙勿用", "早年纹势初定，地纹有根而玉柱未显，正合潜龙养志之象；求学、初业与家庭期许交织，才思虽有，名位未必即彰。宜把根基筑于日常，把未成之志藏于勤行，待风来时自有腾跃之资，莫因一时迟滞而轻弃长程；守拙勤学，终见其用。", "三十岁前，你可能一面想证明自己，一面受学业、初职或家庭期待牵引，常用多做一点来换取安全感；一次挫折也容易被你看成全盘否定。把每次实践带来的能力写下来，主动向可信的人求反馈，让经历慢慢形成方向，你不必急着一次定局。"),
        "middle_years": _stage(timeline_raw.get("middle_years"), "中流砥柱：见龙在田", "三十至五十之间，地纹仍有弧力，人纹越掌而玉柱于中段渐显，乃由试探转为担事之象；职责、合作与取舍相继而来，先承压力，后凭经验开局。宜以厚重守信用，以变通应时机，见龙在田而不忘耕云之本，方能将所学化为可持续的基业。", "三十至五十岁，工作可能从执行走向带人、负责项目或重新选择赛道，过去累积终于需要被组织成方法。忙碌时你容易把决定都集中到自己手里，关系也会因沟通不足而紧绷。明确授权、定期复盘边界，把重要关系纳入时间安排，成就才不以耗尽自己为代价。"),
        "later_years": _stage(timeline_raw.get("later_years"), "晚景秋收：飞龙在天", "五十岁后，地纹入掌底而势渐缓，玉柱上行潜藏，天纹弧意仍存，正是由争先转为收摄、由独任转为传承之气；前半生所学宜化为识人、教人、惜缘之功。莫问高处几重天，留灯照后来者，心宽处便是秋收，余韵自能绵长；知止而后安，福泽自延。", "五十岁后，你更适合把重心从不断争取位置转向分享经验、经营兴趣与筛选真诚关系。若仍习惯独自承担，旧有责任感会遮住新的生活可能，也可能让晚辈感到距离。为自己保留固定爱好，主动传授而不替人包办，与亲友建立轻松稳定的相聚节奏。"),
    }
    return {"observations": observations, "analysis": analysis, "timeline": timeline, "master_pan_ci": _text(raw.get("master_pan_ci") or raw.get("master_quote"), "厚积成势，静守花开", 100)}


async def analyze(prepared, quality_score: float, issues: list[str]) -> PalmistryReport:
    api_key = os.environ.get("AI_API_KEY")
    base_url = os.environ.get("AI_BASE_URL")
    model = os.environ.get("AI_MODEL", "gpt-5.5")
    if not api_key or not base_url:
        raise RuntimeError("AI_API_KEY 或 AI_BASE_URL 未配置")
    rule_version, rules = load_rules()
    system_prompt = """ROLE: 你是一位深谙《麻衣相法》的相学宗师，同时精通现代心理学疗愈。语言古雅、中正而温暖。
TASK: 洞察用户手掌图片中的地纹、人纹、天纹、玉柱纹、家风纹，输出特征观察、五纹解析和早中晚三阶段流年推演。

CRITICAL INSTRUCTIONS:
这是东方传统文化与心理娱乐体验，不是医疗、心理诊断或确定性预测。正文不要反复输出免责声明；服务端最终统一附加。不得输出疾病诊断、寿命判断、心理疾病判断，或要求用户据此作重大人生决策。遇到纹理模糊或不可见，须如实写“隐而不显”“潜藏不露”，不可捏造。
4. 强制字数与深度约束：`analysis` 与 `timeline` 下的每一个 `classical`、`modern` 字段，必须严格控制在 100 到 150 个中文字符之间（不含字段名）。严禁用单句、套话或重复句敷衍；每段都要有具体观察、推演和可读的细节。

RULES:
1. 观察字段只描述可见形态。五纹分别使用 earth、human、heaven、jade、family 作为键。
2. 五纹解析必须同时输出 classical（古雅相理判词）和 modern（通俗、温暖、非诊断性的生活与心理建议）。
3. 引入流年法：沿纹理走势写 early_years（30岁前）、middle_years（30-50岁）、later_years（50岁后），形成有起承转合的文化故事；不得写成确定事件或寿命预测。
4. 古文相理（`classical`）每段必须包含三层逻辑：先以相理术语观象，描述对应纹理的深浅、走向、连续性或隐显；再断事，推演性格倾向、运势节奏或阶段气象；最后落判词，给出含东方哲理的诗意建议。三层要自然融为一段，不要用“第一、第二、第三”机械列举。
5. 白话疗愈（`modern`）每段必须包含三层逻辑：先做现状共鸣，点出可从掌纹象征联想到的性格特质或处境；再做痛点剖析，指出可能的现实困境、关系摩擦或内耗来源；最后给出破局指南，提供可执行的心理调适、沟通、习惯或生活建议。不得写医疗诊断。
6. 流年推演必须有强烈人生故事感：每个阶段的 `classical` 与 `modern` 都要具体描绘事业状态、心智转变或人际关系场景，写出起承转合和前后因果，避免“会越来越好”等空泛套话；仍不得写成确定事件、寿命预测或保证性承诺。
7. master_pan_ci 输出四言或八言传统判词。
8. 只返回一个合法的 json object，不输出 Markdown、思维链或额外字段；必须包含小写 json 这个词对应的 JSON 格式要求。

OUTPUT FORMAT:
{"observations":{"earth":"","human":"","heaven":"","jade":"","family":""},"analysis":{"classical":{"foundation":"","wisdom":"","karma":"","career":"","marriage":""},"modern":{"foundation":"","wisdom":"","karma":"","career":"","marriage":""}},"timeline":{"early_years":{"title":"早年启蒙：潜龙勿用","classical":"","modern":""},"middle_years":{"title":"中流砥柱：见龙在田","classical":"","modern":""},"later_years":{"title":"晚景秋收：飞龙在天","classical":"","modern":""}},"master_pan_ci":""}
"""
    content = [
        {"type": "text", "text": f"{system_prompt}\n规则版本：{rule_version}\n规则摘要：{json.dumps(rules['lines'], ensure_ascii=False)}"},
        {"type": "text", "text": f"内部图像质量问题：{issues or '无'}。请先观察完整概览图，再交叉参考局部图与增强图。"},
        {"type": "text", "text": "视图一：完整掌心概览图，优先判断掌底、掌侧、腕部和整体纹势。"},
        {"type": "image_url", "image_url": {"url": prepared.overview_data_uri, "detail": "low"}},
        {"type": "text", "text": "视图二：宽边界掌心局部图，观察五纹走向。"},
        {"type": "image_url", "image_url": {"url": prepared.crop_data_uri, "detail": "high"}},
        {"type": "text", "text": "视图三：CLAHE 增强图，仅辅助辨认浅纹，不将增强噪声视作真实纹理。"},
        {"type": "image_url", "image_url": {"url": prepared.enhanced_data_uri, "detail": "high"}},
    ]
    payload = {"model": model, "temperature": 0.55, "max_tokens": 3000, "response_format": {"type": "json_object"}, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": content}]}
    timeout = float(os.environ.get("REQUEST_TIMEOUT_SECONDS", "90"))
    try:
        # The desktop environment may expose a stale HTTP(S)_PROXY. The configured
        # AI endpoint is reachable directly, so do not inherit process proxy vars.
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            response = await client.post(_endpoint(base_url), headers={"Authorization": f"Bearer {api_key}"}, json=payload)
            response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise TimeoutError() from exc
    def extract_text(body: dict) -> str:
        value = body["choices"][0]["message"]["content"]
        if isinstance(value, list):
            value = "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in value)
        return value

    text = extract_text(response.json())
    try:
        report = PalmistryReport.model_validate(_normalize_payload(_json_from_text(text)))
    except ValidationError as first_error:
        correction = (
            "上一版 json 未通过长度校验。请只修正并完整重发同一 JSON：analysis 和 timeline 下每个 classical、modern 字段都必须是 100–150 个中文字符；"
            "每段必须包含具体观象/推演/建议或现状共鸣/痛点/破局，不得删减字段，不要输出 Markdown。"
        )
        retry_payload = dict(payload)
        retry_payload["messages"] = list(payload["messages"]) + [{"role": "user", "content": correction}]
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as retry_client:
            retry_response = await retry_client.post(_endpoint(base_url), headers={"Authorization": f"Bearer {api_key}"}, json=retry_payload)
            retry_response.raise_for_status()
        retry_text = extract_text(retry_response.json())
        try:
            report = PalmistryReport.model_validate(_normalize_payload(_json_from_text(retry_text)))
        except ValidationError as second_error:
            raise ValueError(f"模型长文本仍未通过字段长度校验: {second_error}") from first_error
    if any(term in json.dumps(report.model_dump(), ensure_ascii=False) for term in FORBIDDEN):
        raise ValueError("模型输出包含禁止的医疗或确定性结论")
    report.disclaimer = FIXED_DISCLAIMER
    return report
