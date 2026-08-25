from backend.schemas import PalmistryReport


def test_report_schema_accepts_minimal_report():
    classical = "根基观象：地纹回环而深浅相间，见其根气有本；断事而言，早年多在积蓄与试探之间，遇事先守后攻；判曰：藏锋养势，顺时而行。" * 2
    modern = "你往往愿意先把事情想清楚再行动，长期积累是你的优势；真正的压力在于过度自我要求、害怕准备不足；可以把目标拆成每周一步，记录完成而不是只盯着缺口。" * 2
    report = PalmistryReport.model_validate({
        "observations": {
            "earth": "弧线清晰", "human": "横向延展", "heaven": "线条偏浅", "jade": "隐而不显", "family": "潜藏不露",
        },
        "analysis": {
            "classical": {"foundation": classical, "wisdom": classical, "karma": classical, "career": classical, "marriage": classical},
            "modern": {"foundation": modern, "wisdom": modern, "karma": modern, "career": modern, "marriage": modern},
        },
        "timeline": {
            "early_years": {"title": "早年", "classical": classical, "modern": modern},
            "middle_years": {"title": "中年", "classical": classical, "modern": modern},
            "later_years": {"title": "晚年", "classical": classical, "modern": modern},
        },
        "master_pan_ci": "潜龙在渊",
    })
    assert len(report.analysis.modern.career) >= 100
    assert len(report.timeline.early_years.classical) >= 100
    assert report.master_pan_ci == "潜龙在渊"
