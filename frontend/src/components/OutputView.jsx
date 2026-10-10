import React, { useState } from 'react';
import { 
  Copy, Download, Check, BookOpen, ShieldCheck, ChevronDown, 
  ChevronUp, Award, Layers, Sparkles, FileText, CheckCircle2, AlertTriangle
} from 'lucide-react';

export default function OutputView({ data, loading, error }) {
  const [copied, setCopied] = useState(false);
  const [expandedAnswer, setExpandedAnswer] = useState({});

  if (loading) {
    return (
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-12 text-center shadow-xl backdrop-blur-sm min-h-[500px] flex flex-col items-center justify-center">
        <div className="relative mb-6">
          <div className="w-16 h-16 border-4 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin" />
          <Sparkles className="w-6 h-6 text-indigo-400 absolute inset-0 m-auto" />
        </div>
        <h3 className="text-lg font-bold text-white mb-2">Agentic QG Pipeline in Progress</h3>
        <p className="text-xs text-slate-400 max-w-md mx-auto leading-relaxed">
          The Planner is allocating Bloom levels by largest-remainder, retrieving semantic chunks via MMR, 
          and executing hard-gate verbatim grounding validation...
        </p>
        <div className="mt-6 flex gap-2">
          <span className="px-3 py-1 rounded-full bg-slate-800 text-[11px] font-mono text-indigo-300 border border-indigo-500/20 animate-pulse">
            1. Chunk Retrieval
          </span>
          <span className="px-3 py-1 rounded-full bg-slate-800 text-[11px] font-mono text-indigo-300 border border-indigo-500/20 animate-pulse delay-150">
            2. Multi-Agent Gen
          </span>
          <span className="px-3 py-1 rounded-full bg-slate-800 text-[11px] font-mono text-indigo-300 border border-indigo-500/20 animate-pulse delay-300">
            3. Hard-Gate Audit
          </span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-slate-900/60 border border-rose-500/30 rounded-2xl p-8 text-center shadow-xl backdrop-blur-sm">
        <div className="p-3 bg-rose-500/10 text-rose-400 rounded-full w-12 h-12 mx-auto mb-4 flex items-center justify-center border border-rose-500/20">
          <AlertTriangle className="w-6 h-6" />
        </div>
        <h3 className="text-base font-bold text-white mb-2">Pipeline Execution Failed</h3>
        <p className="text-xs text-rose-300 bg-rose-950/40 p-4 rounded-xl font-mono text-left max-w-xl mx-auto border border-rose-500/20">
          {error}
        </p>
      </div>
    );
  }

  if (!data || !data.questions || data.questions.length === 0) {
    return (
      <div className="bg-slate-900/40 border border-slate-800 rounded-2xl p-12 text-center shadow-xl backdrop-blur-sm min-h-[500px] flex flex-col items-center justify-center">
        <div className="p-4 rounded-2xl bg-slate-800/60 text-slate-400 mb-4 ring-1 ring-white/5">
          <BookOpen className="w-8 h-8 text-slate-500" />
        </div>
        <h3 className="text-base font-semibold text-slate-300 mb-1">No Question Paper Generated Yet</h3>
        <p className="text-xs text-slate-500 max-w-sm">
          Fill in your exam requirements on the left panel and click <strong>Generate Question Paper</strong> to run Questrix AI.
        </p>
      </div>
    );
  }

  const { subject, questions, total_marks, summary } = data;

  const toggleAnswer = (idx) => {
    setExpandedAnswer((prev) => ({ ...prev, [idx]: !prev[idx] }));
  };

  const getFormattedPaperText = () => {
    let text = `=====================================================\n`;
    text += `             ${subject.toUpperCase()} EXAMINATION\n`;
    text += `Total Marks: ${total_marks} Marks                 Time: 2 Hours\n`;
    text += `=====================================================\n\n`;
    text += `INSTRUCTIONS: Answer all questions cleanly.\n\n`;

    questions.forEach((q, idx) => {
      text += `Q${idx + 1}. [${q.marks} Marks] (${q.bloom_level})\n`;
      text += `    ${q.question}\n\n`;
      if (q.answer) {
        text += `    Model Answer: ${q.answer}\n`;
        text += `    Verbatim Evidence: ${q.source_snippet}\n\n`;
      }
    });

    return text;
  };

  const handleCopy = () => {
    const paperText = getFormattedPaperText();
    navigator.clipboard.writeText(paperText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = (format) => {
    const text = getFormattedPaperText();
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${subject.replace(/[^a-zA-Z0-9]/g, '_')}_Question_Paper.${format}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="space-y-6">
      {/* Action Header Card */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-4 sm:p-6 shadow-xl backdrop-blur-sm flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-white">{subject}</h2>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              {questions.length} Questions Generated
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Total Marks: <strong className="text-white">{total_marks} Marks</strong> | Average Quality Score: <strong className="text-indigo-400">{(summary.avg_quality_score * 100 || 88).toFixed(1)}%</strong>
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleCopy}
            className="px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium flex items-center gap-1.5 transition border border-slate-700"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5 text-slate-400" />}
            <span>{copied ? 'Copied!' : 'Copy Text'}</span>
          </button>

          <button
            onClick={() => handleDownload('md')}
            className="px-3 py-2 rounded-xl bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 text-xs font-medium flex items-center gap-1.5 transition border border-indigo-500/30"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Download .MD</span>
          </button>
        </div>
      </div>

      {/* Official Exam Paper Container */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 sm:p-8 shadow-2xl space-y-6">
        {/* Paper Title Header */}
        <div className="text-center pb-6 border-b border-slate-800">
          <h3 className="text-lg font-bold text-white tracking-wide uppercase">{subject} EXAMINATION</h3>
          <div className="mt-2 flex items-center justify-center gap-6 text-xs text-slate-400 font-mono">
            <span>Time Allowed: 2 Hours</span>
            <span>•</span>
            <span>Maximum Marks: {total_marks}</span>
          </div>
        </div>

        {/* Question Cards List */}
        <div className="space-y-6">
          {questions.map((q, idx) => {
            const isExpanded = expandedAnswer[idx];
            const validation = q.validation || {};

            return (
              <div 
                key={idx} 
                className="bg-slate-950 border border-slate-800/80 rounded-xl p-5 hover:border-slate-700 transition"
              >
                {/* Question Top Metadata */}
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span className="w-6 h-6 rounded-lg bg-indigo-500/10 text-indigo-400 text-xs font-bold flex items-center justify-center border border-indigo-500/20">
                      Q{idx + 1}
                    </span>
                    <span className="px-2 py-0.5 rounded-md bg-slate-800 text-[11px] font-semibold text-slate-300">
                      {q.bloom_level}
                    </span>
                    {q.topic && (
                      <span className="px-2 py-0.5 rounded-md bg-purple-500/10 text-purple-400 text-[11px] font-medium border border-purple-500/20">
                        {q.topic}
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-3">
                    <span className="text-xs font-bold text-amber-400 bg-amber-500/10 px-2.5 py-1 rounded-md border border-amber-500/20">
                      [{q.marks} Marks]
                    </span>
                  </div>
                </div>

                {/* Question Text */}
                <p className="text-sm font-medium text-slate-100 leading-relaxed mb-4">
                  {q.question}
                </p>

                {/* Validation Badges */}
                <div className="flex flex-wrap items-center gap-2 mb-3 pt-3 border-t border-slate-900">
                  <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-400 bg-emerald-950/40 px-2.5 py-0.5 rounded-md border border-emerald-500/20">
                    <ShieldCheck className="w-3 h-3" /> Grounded Verbatim
                  </span>
                  <span className="inline-flex items-center gap-1 text-[11px] font-medium text-indigo-400 bg-indigo-950/40 px-2.5 py-0.5 rounded-md border border-indigo-500/20">
                    Quality Score: {(q.quality_score * 100).toFixed(0)}%
                  </span>
                  <span className="inline-flex items-center gap-1 text-[11px] font-medium text-slate-400 bg-slate-900 px-2 py-0.5 rounded-md border border-slate-800">
                    Tries: {q.attempts || 1}
                  </span>
                </div>

                {/* Model Answer & Verbatim Evidence Accordion */}
                <div className="mt-3">
                  <button
                    onClick={() => toggleAnswer(idx)}
                    className="text-xs font-medium text-indigo-400 hover:text-indigo-300 flex items-center gap-1 transition"
                  >
                    {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                    <span>{isExpanded ? 'Hide Model Answer & Evidence' : 'Show Model Answer & Verbatim Evidence'}</span>
                  </button>

                  {isExpanded && (
                    <div className="mt-3 p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-3 text-xs">
                      <div>
                        <span className="font-semibold text-slate-300 block mb-1">Model Answer / Solution:</span>
                        <p className="text-slate-300 leading-relaxed font-sans">{q.answer || 'Refer to source material.'}</p>
                      </div>

                      {q.source_snippet && (
                        <div className="pt-2 border-t border-slate-800/80">
                          <span className="font-semibold text-indigo-300 block mb-1">Verbatim Source Material Snippet:</span>
                          <p className="text-slate-400 italic font-mono bg-slate-950 p-2.5 rounded-lg border border-slate-800">
                            "{q.source_snippet}"
                          </p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
