import json
import os
import re

import httpx
import yaml

from .schemas import PalmistryReport


FIXED_DISCLAIMER = "本卷轴由 AI 结合传统易理相学生成，仅供国学文化交流与雅玩，不作现代医学或人生决策之用。"
FORBIDDEN = ("疾病诊断", "寿命预测", "心脏病", "癌症", "抑郁症", "焦虑症", "一定会", "注定", "智商")


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


def _quality_label(score: float) -> str:
    return "High" if score >= 0.75 else "Medium" if score >= 0.5 else "Low"


def _text(value: object, fallback: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, dict):
        return "；".join(f"{k}：{v}" for k, v in value.items() if v)[:700] or fallback
    return fallback


def _normalize_payload(raw: dict, quality_score: float) -> dict:
    """Normalize the 三才纹 schema and tolerate older model responses."""
    old_lines = ("life_line", "head_line", "heart_line")
    new_lines = ("earth_line", "human_line", "heaven_line", "jade_pillar_line", "family_ethos_line")
    source = raw.get("observations") if isinstance(raw.get("observations"), (dict, list)) else raw
    if isinstance(source, list):
        source = dict(zip(old_lines, source))
    source = source if isinstance(source, dict) else {}
    observations = {}
    for new, old in zip(new_lines[:3], old_lines):
        item = source.get(new, source.get(old, {}))
        if isinstance(item, dict) and "description" in item:
            item = item["description"]
        elif isinstance(item, dict) and isinstance(item.get("observations"), dict):
            item = item["observations"]
        observations[new] = _text(item, "纹理幽微，尚待更清晰的掌面影像以观其势。")
    observations["jade_pillar_line"] = _text(source.get("jade_pillar_line"), "玉柱纹隐而不显，事业之势尚藏于掌底，宜静观其变、厚积而后发。")
    observations["family_ethos_line"] = _text(source.get("family_ethos_line"), "家风纹潜藏不露，姻缘之机不宜强求，顺应天时自有相逢。")

    analysis = raw.get("analysis") if isinstance(raw.get("analysis"), dict) else {}
    old_analysis = raw.get("traditional_interpretation") if isinstance(raw.get("traditional_interpretation"), dict) else {}
    normalized_analysis = {
        "foundation": _text(analysis.get("foundation") or old_analysis.get("health_energy") or old_analysis.get("生命线"), "地纹回环，如山河有根；根基稳处，自有生发之机。"),
        "wisdom": _text(analysis.get("wisdom") or old_analysis.get("career_mind") or old_analysis.get("智慧线"), "人纹横展，心智自有章法；藏锋守拙，方能谋定而后动。"),
        "karma": _text(analysis.get("karma") or old_analysis.get("emotional_status") or old_analysis.get("感情线"), "天纹牵情，所念皆有回响；守一分真心，便得一方清宁。"),
        "career": _text(analysis.get("career"), "玉柱纹隐而不显，基业之机尚在潜藏；守拙蓄力，待时而动。"),
        "marriage": _text(analysis.get("marriage"), "家风纹潜藏不露，姻缘宜顺其自然；守真守正，自有良缘相契。"),
    }
    technical = raw.get("technical_metrics") if isinstance(raw.get("technical_metrics"), dict) else {}
    quality = technical.get("image_quality") if technical.get("image_quality") in {"High", "Medium", "Low"} else _quality_label(quality_score)
    try:
        confidence = max(0, min(100, int(technical.get("confidence_score", round(quality_score * 100)))))
    except (TypeError, ValueError):
        confidence = round(quality_score * 100)
    return {
        "technical_metrics": {"image_quality": quality, "confidence_score": confidence},
        "observations": observations,
        "analysis": normalized_analysis,
        "master_pan_ci": _text(raw.get("master_pan_ci") or raw.get("master_quote"), "潜龙在渊，静待时飞"),
    }


async def analyze(prepared, quality_score: float, issues: list[str]) -> PalmistryReport:
    api_key = os.environ.get("AI_API_KEY")
    base_url = os.environ.get("AI_BASE_URL")
    model = os.environ.get("AI_MODEL", "gpt-5.5")
    if not api_key or not base_url:
        raise RuntimeError("AI_API_KEY 或 AI_BASE_URL 未配置")
    rule_version, rules = load_rules()
    system_prompt = """ROLE: 你是一位深谙《麻衣相法》《柳庄相法》等中国传统相学经典的相学宗师。你通晓易理与阴阳五行，语言古雅、中正，充满东方哲理与国学底蕴。
TASK: 洞察用户手掌纹理，观其形而知其势，生成兼具传统底蕴与正向情绪价值的相学批语。

CRITICAL INSTRUCTIONS:
这是东方传统文化互动体验，不是现代医疗或专业心理预测。正文不要反复输出免责声明；系统最终界面统一展示一次。不得输出疾病诊断、寿命判断、心理疾病判断，或要求用户据此作重大人生决策。遇到杂乱、断裂或模糊纹理，用“破而后立、顺势重组、寒彻骨后见梅香”等积极而不确定的表达，不编造不可见细节。

RULES:
1. 术语转换：生命线称“地纹”，智慧线称“人纹”，感情线称“天纹”。
2. observations 准确描述三才纹的深浅、长短、走向、分叉、岛状和连续性。
3. 新增纹理识别：玉柱纹（事业线）为掌底向中指下方延伸的纵向纹理，论事业起伏、基业开拓与社会成就；家风纹（婚姻线）为小指根部侧面与天纹之间的短横纹，论姻缘际会、伴侣羁绊与成家立业之机。若极浅或不可见，明确写“隐而不显”或“潜藏不露”，并给出对应的象征性解释，切勿捏造。
4. analysis 分别论断“根基禀赋与生命本源能量”“心智悟性与行事谋略格局”“情志因缘与内心执念”“事业起伏与基业开拓”“姻缘际会与伴侣羁绊”，使用古雅而温和的语言。
5. master_pan_ci 输出一句四言或八言传统判词。
6. 只返回一个合法的 json object，不输出 Markdown、思维链或额外字段。

OUTPUT FORMAT:
{"technical_metrics":{"image_quality":"High|Medium|Low","confidence_score":0},"observations":{"earth_line":"","human_line":"","heaven_line":"","jade_pillar_line":"","family_ethos_line":""},"analysis":{"foundation":"","wisdom":"","karma":"","career":"","marriage":""},"master_pan_ci":""}
"""
    content = [
        {"type": "text", "text": f"{system_prompt}\n规则版本：{rule_version}\n规则摘要：{json.dumps(rules['lines'], ensure_ascii=False)}"},
        {"type": "text", "text": f"内部图像质量：{_quality_label(quality_score)}；问题：{issues or '无'}"},
        # The crop and CLAHE view contain the relevant palm evidence. Avoid sending
        # the duplicate full-resolution original to reduce upstream vision latency.
        {"type": "image_url", "image_url": {"url": prepared.crop_data_uri, "detail": "high"}},
        {"type": "image_url", "image_url": {"url": prepared.enhanced_data_uri, "detail": "high"}},
    ]
    payload = {"model": model, "temperature": 0.55, "response_format": {"type": "json_object"}, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": content}]}
    # Vision requests can take longer than text-only calls; keep the browser waiting
    # instead of converting a valid but slow upstream response into a false 504.
    timeout = float(os.environ.get("REQUEST_TIMEOUT_SECONDS", "90"))
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(_endpoint(base_url), headers={"Authorization": f"Bearer {api_key}"}, json=payload)
            response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise TimeoutError() from exc
    text = response.json()["choices"][0]["message"]["content"]
    if isinstance(text, list):
        text = "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in text)
    report = PalmistryReport.model_validate(_normalize_payload(_json_from_text(text), quality_score))
    if any(term in json.dumps(report.model_dump(), ensure_ascii=False) for term in FORBIDDEN):
        raise ValueError("模型输出包含禁止的医疗或确定性结论")
    report.disclaimer = FIXED_DISCLAIMER
    return report
