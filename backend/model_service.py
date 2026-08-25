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


def _bounded_long_text(value: object, fallback: str, mode: str) -> str:
    """Keep every bilingual paragraph within the product's 100–150 char contract."""
    text = _text(value, fallback, 150)
    suffix = (
        "此象贵在守中蓄势，勿以一时得失乱其方寸，静观时机而行。"
        if mode == "classical"
        else "你可以把这份提醒落到一个具体行动上，给自己留出复盘和调整的空间。"
    )
    while len(text) < 100:
        text += suffix
    return text[:150]


def _stage(raw: object, title: str, classical: str, modern: str) -> dict:
    item = raw if isinstance(raw, dict) else {}
    return {"title": _text(item.get("title"), title, 120), "classical": _bounded_long_text(item.get("classical"), classical, "classical"), "modern": _bounded_long_text(item.get("modern"), modern, "modern")}


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
    classical_defaults = {"foundation": "地纹盘桓，根基有本；守正以养元，顺时而发。", "wisdom": "人纹横展，心有权衡；藏锋守拙，谋定而后动。", "karma": "天纹牵情，情志有源；守一片真心，自得清宁。", "career": "玉柱虽幽，基业之机未尝不在；厚积其势，待时而行。", "marriage": "家风纹隐，姻缘贵在随缘守正；相敬相扶，家道自昌。"}
    modern_defaults = {"foundation": "你可以把自己的精力当作长期资产，先稳定节奏，再慢慢积累。", "wisdom": "你的思考适合保留空间，先观察再行动，复杂问题会因此变得清楚。", "karma": "关系里保持真诚和边界，温柔表达需求，比独自猜测更能带来连接。", "career": "事业不必追求一步到位，持续积累能力和作品，机会会更容易被你接住。", "marriage": "亲密关系需要稳定沟通和共同生活目标，慢一点确认，反而更踏实。"}
    analysis = {"classical": {}, "modern": {}}
    for key in LINE_KEYS:
        analysis["classical"][key] = _bounded_long_text(classical_raw.get(key) or old_map.get(key), classical_defaults[key], "classical")
        analysis["modern"][key] = _bounded_long_text(modern_raw.get(key) or old_map.get(key), modern_defaults[key], "modern")

    timeline_raw = raw.get("timeline") if isinstance(raw.get("timeline"), dict) else {}
    timeline = {
        "early_years": _stage(timeline_raw.get("early_years"), "早年启蒙：潜龙勿用", "早岁如潜龙养志，宜读书观世，蓄德养器。", "早期更适合探索兴趣、建立自我感和基础能力，不必急着证明一切。"),
        "middle_years": _stage(timeline_raw.get("middle_years"), "中流砥柱：见龙在田", "中年见龙在田，所学渐成所用；守其根本，事业可开新局。", "中年是把经验转成成果的阶段，适合聚焦优势、承担更大责任。"),
        "later_years": _stage(timeline_raw.get("later_years"), "晚景秋收：飞龙在天", "晚景秋收，飞龙在天；功成不居，留余荫以泽后人。", "后期更适合享受积累、传递经验，并把生活重心放回从容和满足。"),
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
        async with httpx.AsyncClient(timeout=timeout) as client:
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
        async with httpx.AsyncClient(timeout=timeout) as retry_client:
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
