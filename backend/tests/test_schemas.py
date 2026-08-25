from backend.schemas import PalmistryReport


def test_report_schema_accepts_minimal_report():
    report = PalmistryReport.model_validate({
        "observations": {
            "earth": "弧线清晰", "human": "横向延展", "heaven": "线条偏浅", "jade": "隐而不显", "family": "潜藏不露",
        },
        "analysis": {
            "classical": {"foundation": "根基稳", "wisdom": "思路开阔", "karma": "心有柔光", "career": "厚积而发", "marriage": "顺其自然"},
            "modern": {"foundation": "节奏稳定", "wisdom": "思路开阔", "karma": "真诚沟通", "career": "持续积累", "marriage": "共同成长"},
        },
        "timeline": {
            "early_years": {"title": "早年", "classical": "潜龙勿用", "modern": "探索成长"},
            "middle_years": {"title": "中年", "classical": "见龙在田", "modern": "经验成势"},
            "later_years": {"title": "晚年", "classical": "飞龙在天", "modern": "从容收获"},
        },
        "master_pan_ci": "潜龙在渊",
    })
    assert report.analysis.modern.career == "持续积累"
    assert report.timeline.early_years.classical == "潜龙勿用"
    assert report.master_pan_ci == "潜龙在渊"
