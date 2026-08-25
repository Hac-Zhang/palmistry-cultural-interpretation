import { useState } from "react";

const DISCLAIMER = "本卷轴由 AI 结合传统易理相学生成，仅供国学文化交流与雅玩，不作现代医学或人生决策之用。";

export default function PalmistryResult({ report }) {
  const [open, setOpen] = useState(false);
  const observations = report?.observations ?? {};
  const analysis = report?.analysis ?? {};
  const cards = [["根基 · 地纹", analysis?.foundation], ["心智 · 人纹", analysis?.wisdom], ["因缘 · 天纹", analysis?.karma], ["基业 · 玉柱纹", analysis?.career], ["姻缘 · 家风纹", analysis?.marriage]];
  return (
    <section className="relative mx-auto max-w-5xl overflow-hidden bg-[#f4eedf] p-6 text-[#211e1a] shadow-2xl md:p-12">
      <div className="pointer-events-none absolute inset-3 border border-[#7d2d2d]/35" />
      <div className="relative text-center"><p className="mb-5 text-xs tracking-[0.45em] text-[#56707b]">观掌 · 观势 · 观心</p><div className="mx-auto inline-block border-2 border-[#9d3030] p-3 text-[#9d3030] shadow-[3px_3px_0_#9d3030]"><h2 className="font-serif text-4xl leading-tight md:text-6xl">{report?.master_pan_ci || "潜龙在渊，静待时飞"}</h2><p className="mt-2 text-xs tracking-[0.35em]">五纹批语</p></div></div>
      <div className="relative mt-10 grid gap-5 md:grid-cols-6">{cards.map(([title, text], index) => <article key={title} className={`border border-[#2f2922]/20 bg-[#fbf7ed]/80 p-6 shadow-[inset_0_0_35px_rgba(80,60,35,.07)] md:col-span-2 ${index === 3 ? "md:col-start-2" : ""}`}><h3 className="mb-4 font-serif text-xl text-[#7d2d2d]">{title}</h3><p className="font-serif leading-8 text-[#39332b]">{text || "暂无释义"}</p></article>)}</div>
      <button type="button" onClick={() => setOpen((value) => !value)} className="relative mt-8 border-b border-[#56707b]/50 pb-1 font-serif text-sm text-[#56707b]">{open ? "收起相理依据" : "观相明细 · 探源相理依据"}</button>
      {open && <div className="relative mt-5 border-l-2 border-[#9d3030]/50 pl-5 font-serif text-sm leading-8 text-[#655d51]"><p><b className="text-[#7d2d2d]">地纹：</b>{observations?.earth_line || "暂无观测"}</p><p><b className="text-[#7d2d2d]">人纹：</b>{observations?.human_line || "暂无观测"}</p><p><b className="text-[#7d2d2d]">天纹：</b>{observations?.heaven_line || "暂无观测"}</p><p><b className="text-[#7d2d2d]">玉柱纹：</b>{observations?.jade_pillar_line || "暂无观测"}</p><p><b className="text-[#7d2d2d]">家风纹：</b>{observations?.family_ethos_line || "暂无观测"}</p></div>}
      <p className="relative mt-10 text-center font-serif text-xs leading-6 text-[#8b8274]">{report?.disclaimer || DISCLAIMER}</p>
    </section>
  );
}
