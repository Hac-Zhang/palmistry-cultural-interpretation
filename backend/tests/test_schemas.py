from backend.schemas import PalmistryReport


def test_report_schema_accepts_minimal_report():
    report = PalmistryReport.model_validate({
        "technical_metrics": {"image_quality": "High", "confidence_score": 86},
        "observations": {
            "earth_line": "弧线清晰",
            "human_line": "横向延展",
            "heaven_line": "线条偏浅",
            "jade_pillar_line": "隐而不显",
            "family_ethos_line": "潜藏不露",
        },
        "analysis": {"foundation": "根基稳", "wisdom": "思路开阔", "karma": "心有柔光", "career": "厚积而发", "marriage": "顺其自然"},
        "master_pan_ci": "潜龙在渊",
    })
    assert report.technical_metrics.confidence_score == 86
    assert report.master_pan_ci == "潜龙在渊"
