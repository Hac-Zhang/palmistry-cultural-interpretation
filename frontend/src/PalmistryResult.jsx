import { useState } from "react";

const DISCLAIMER = "本卷轴由 AI 结合传统易理相学生成，仅供国学文化交流与雅玩，不作现代医学或人生决策之用。";

export async function requestPalmistryAnalysis(file, options = {}) {
  if (!file) throw new Error("请先选择掌心照片");
  const form = new FormData();
  form.append("image", file);
  const response = await fetch("/api/v1/palmistry/analyze", { method: "POST", body: form, signal: options.signal });
  const raw = await response.text();
  let responseData;
  try { responseData = raw ? JSON.parse(raw) : {}; } catch { responseData = raw; }
  console.log("后端返回的原始数据:", responseData);
  if (!response.ok) throw new Error(responseData?.detail?.error?.message || responseData?.error?.message || "天机受阻，请稍后再试");
  return responseData;
}

export default function PalmistryResult({ report }) {
  const [languageMode, setLanguageMode] = useState("classical");
  const [open, setOpen] = useState(false);
  const analysis = report?.analysis?.[languageMode] ?? {};
  const observations = report?.observations ?? {};
  const timeline = report?.timeline ?? {};
  const cards = [["根基 · 地纹", analysis?.foundation], ["心智 · 人纹", analysis?.wisdom], ["因缘 · 天纹", analysis?.karma], ["基业 · 玉柱纹", analysis?.career], ["姻缘 · 家风纹", analysis?.marriage]];
  const stages = [["early_years", timeline?.early_years], ["middle_years", timeline?.middle_years], ["later_years", timeline?.later_years]];
  return (
    <section className="relative mx-auto max-w-5xl overflow-hidden bg-[#f4eedf] p-6 text-[#211e1a] shadow-2xl md:p-12">
      <div className="pointer-events-none absolute inset-3 border border-[#7d2d2d]/35" />
      <div className="relative text-center"><p className="mb-5 text-xs tracking-[0.45em] text-[#56707b]">观掌 · 观势 · 观心</p><div className="mx-auto inline-block border-2 border-[#9d3030] p-3 text-[#9d3030] shadow-[3px_3px_0_#9d3030]"><h2 className="font-serif text-4xl leading-tight md:text-6xl">{report?.master_pan_ci || "厚积成势，静守花开"}</h2><p className="mt-2 text-xs tracking-[0.35em]">五纹批语</p></div>
        <div className="mx-auto mt-5 inline-flex border border-[#9d3030]/40 bg-[#fbf7ed] p-1 font-serif text-sm"><button type="button" onClick={() => setLanguageMode("classical")} className={`px-4 py-2 ${languageMode === "classical" ? "bg-[#9d3030] text-white" : "text-[#7d2d2d]"}`}>文言相理</button><button type="button" onClick={() => setLanguageMode("modern")} className={`px-4 py-2 ${languageMode === "modern" ? "bg-[#56707b] text-white" : "text-[#56707b]"}`}>白话疗愈</button></div>
      </div>
      <div className="relative mt-10 grid gap-5 md:grid-cols-6">{cards.map(([title, text], index) => <article key={title} className={`border border-[#2f2922]/20 bg-[#fbf7ed]/80 p-6 shadow-[inset_0_0_35px_rgba(80,60,35,.07)] md:col-span-2 ${index === 3 ? "md:col-start-2" : ""}`}><h3 className="mb-4 font-serif text-xl text-[#7d2d2d]">{title}</h3><p className="font-serif leading-8 text-[#39332b]">{text || "暂无释义"}</p></article>)}</div>
      <div className="relative mt-14"><h3 className="mb-8 text-center font-serif text-2xl text-[#7d2d2d]">流年推演 · 命轨时间轴</h3><div className="relative ml-3 border-l-2 border-[#9d3030]/45 pl-7">{stages.map(([key, stage]) => <article key={key} className="relative mb-8"><span className="absolute -left-[37px] top-2 h-4 w-4 rounded-full border-4 border-[#f4eedf] bg-[#9d3030]" /><div className="border border-[#2f2922]/20 bg-[#fbf7ed]/80 p-5"><h4 className="font-serif text-lg text-[#7d2d2d]">{stage?.title || "流年一章"}</h4><p className="mt-3 font-serif leading-8 text-[#39332b]">{stage?.[languageMode] || "暂无推演"}</p></div></article>)}</div></div>
      <button type="button" onClick={() => setOpen((value) => !value)} className="relative mt-4 border-b border-[#56707b]/50 pb-1 font-serif text-sm text-[#56707b]">{open ? "收起相理依据" : "观相明细 · 探源相理依据"}</button>
      {open && <div className="relative mt-5 border-l-2 border-[#9d3030]/50 pl-5 font-serif text-sm leading-8 text-[#655d51]"><p><b className="text-[#7d2d2d]">地纹：</b>{observations?.earth || "暂无观测"}</p><p><b className="text-[#7d2d2d]">人纹：</b>{observations?.human || "暂无观测"}</p><p><b className="text-[#7d2d2d]">天纹：</b>{observations?.heaven || "暂无观测"}</p><p><b className="text-[#7d2d2d]">玉柱纹：</b>{observations?.jade || "暂无观测"}</p><p><b className="text-[#7d2d2d]">家风纹：</b>{observations?.family || "暂无观测"}</p></div>}
      <p className="relative mt-10 text-center font-serif text-xs leading-6 text-[#8b8274]">{report?.disclaimer || DISCLAIMER}</p>
    </section>
  );
}
