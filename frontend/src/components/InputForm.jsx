import React, { useState, useEffect, useRef } from 'react';
import { 
  FileText, Upload, Sparkles, Check, AlertCircle, 
  Layers, HelpCircle, BookOpen, Sliders, CheckSquare, Zap, RefreshCw
} from 'lucide-react';
import { ingestDocument, getJobStatus, getLatestIngestionStatus } from '../api/client';

const BLOOM_OPTIONS = [
  { id: 'Remember', label: 'Remember', color: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' },
  { id: 'Understand', label: 'Understand', color: 'bg-blue-500/10 text-blue-400 border-blue-500/30' },
  { id: 'Apply', label: 'Apply', color: 'bg-indigo-500/10 text-indigo-400 border-indigo-500/30' },
  { id: 'Analyze', label: 'Analyze', color: 'bg-purple-500/10 text-purple-400 border-purple-500/30' },
  { id: 'Evaluate', label: 'Evaluate', color: 'bg-amber-500/10 text-amber-400 border-amber-500/30' },
  { id: 'Create', label: 'Create', color: 'bg-rose-500/10 text-rose-400 border-rose-500/30' },
];

function formatBytes(bytes, decimals = 1) {
  if (!bytes || bytes === 0) return '0 Bytes';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

export default function InputForm({ onSubmit, loading }) {
  const [subject, setSubject] = useState('Data Structures & Algorithms');
  const [file, setFile] = useState(null);
  const [numQuestions, setNumQuestions] = useState(6);
  const [concepts, setConcepts] = useState('Arrays, Linked Lists, Stacks, Binary Trees, Graph Traversal, Sorting');
  const [difficulty, setDifficulty] = useState('Medium');
  const [questionType, setQuestionType] = useState('Descriptive');
  const [selectedBloom, setSelectedBloom] = useState(['Understand', 'Apply', 'Analyze']);
  const [marksPerQuestion, setMarksPerQuestion] = useState(5);
  
  // Job & Ingestion states
  const [activeJobId, setActiveJobId] = useState(null);
  const [jobStatus, setJobStatus] = useState(null); // { status, progress, stage, error, chunks_added, concepts }
  const [ingestionReady, setIngestionReady] = useState(false);
  const [totalChunksCount, setTotalChunksCount] = useState(0);

  const pollIntervalRef = useRef(null);

  // Check initial store state on mount
  useEffect(() => {
    async function checkStoreState() {
      const res = await getLatestIngestionStatus();
      if (res && res.total_chunks > 0) {
        setIngestionReady(true);
        setTotalChunksCount(res.total_chunks);
        if (res.latest_job) {
          setJobStatus(res.latest_job);
        }
      }
    }
    checkStoreState();

    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, []);

  // Poll active job status
  useEffect(() => {
    if (!activeJobId) return;

    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);

    pollIntervalRef.current = setInterval(async () => {
      try {
        const job = await getJobStatus(activeJobId);
        setJobStatus(job);

        if (job.status === 'completed') {
          clearInterval(pollIntervalRef.current);
          setIngestionReady(true);
          setTotalChunksCount(job.chunks_added || 0);
        } else if (job.status === 'failed') {
          clearInterval(pollIntervalRef.current);
          setIngestionReady(false);
        }
      } catch (err) {
        console.error('Polling error:', err);
      }
    }, 1500);

    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, [activeJobId]);

  const handleBloomToggle = (level) => {
    if (selectedBloom.includes(level)) {
      if (selectedBloom.length === 1) return; // Keep at least 1
      setSelectedBloom(selectedBloom.filter(b => b !== level));
    } else {
      setSelectedBloom([...selectedBloom, level]);
    }
  };

  const handleFileChange = async (e) => {
    const selectedFile = e.target.files[0];
    if (!selectedFile) return;
    setFile(selectedFile);
    await startIngestionProcess(selectedFile, concepts);
  };

  const startIngestionProcess = async (fileToIngest, conceptsToIngest) => {
    setIngestionReady(false);
    setJobStatus({
      status: 'queued',
      progress: 0.0,
      stage: 'Uploading document file to backend...',
      error: null
    });

    try {
      const res = await ingestDocument(fileToIngest, conceptsToIngest);
      setActiveJobId(res.job_id);
      setJobStatus({
        status: res.status || 'queued',
        progress: 2.0,
        stage: 'Ingestion job queued on Python service...',
        filename: res.filename,
        filesize: res.filesize,
        error: null
      });
    } catch (err) {
      setJobStatus({
        status: 'failed',
        progress: 0.0,
        stage: 'Upload Failed',
        error: err.message
      });
      setIngestionReady(false);
    }
  };

  const handleRetry = () => {
    if (file) {
      startIngestionProcess(file, concepts);
    }
  };

  const handleQuickPreset = async (type) => {
    if (type === 'java') {
      setSubject('Java Object Oriented Programming');
      setConcepts('Inheritance, Polymorphism, Encapsulation, Abstraction, Interfaces');
      setDifficulty('Medium');
      setQuestionType('Descriptive');
      setSelectedBloom(['Understand', 'Apply', 'Analyze']);
      setMarksPerQuestion(10);
    } else if (type === 'ds') {
      setSubject('Data Structures & Algorithms');
      setConcepts('Arrays, Linked Lists, Stacks, Binary Trees, Graph Traversal, Sorting');
      setDifficulty('Hard');
      setQuestionType('Descriptive');
      setSelectedBloom(['Apply', 'Analyze', 'Evaluate']);
      setMarksPerQuestion(5);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!ingestionReady && totalChunksCount === 0) return;
    onSubmit({
      subject,
      num_questions: numQuestions,
      concepts,
      bloom_levels: selectedBloom,
      difficulty,
      question_type: questionType,
      marks_per_question: marksPerQuestion,
    });
  };

  const isProcessing = jobStatus && (jobStatus.status === 'queued' || jobStatus.status === 'processing');
  const isFailed = jobStatus && jobStatus.status === 'failed';
  const isCompleted = jobStatus && jobStatus.status === 'completed';

  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 shadow-xl backdrop-blur-sm">
      <div className="flex items-center justify-between pb-5 border-b border-slate-800 mb-6">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
            <Sliders className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-white">Paper Requirements</h2>
            <p className="text-xs text-slate-400">Configure parameters for agentic QG pipeline</p>
          </div>
        </div>

        {/* Preset quick buttons */}
        <div className="flex gap-1.5">
          <button
            type="button"
            onClick={() => handleQuickPreset('ds')}
            className="px-2.5 py-1 text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg transition"
          >
            DS Preset
          </button>
          <button
            type="button"
            onClick={() => handleQuickPreset('java')}
            className="px-2.5 py-1 text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg transition"
          >
            Java Preset
          </button>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Subject Name */}
        <div>
          <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
            Subject Name <span className="text-rose-400">*</span>
          </label>
          <div className="relative">
            <BookOpen className="w-4 h-4 text-slate-500 absolute left-3.5 top-3" />
            <input
              type="text"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="e.g. Operating Systems"
              required
              className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-10 pr-4 py-2.5 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition"
            />
          </div>
        </div>

        {/* Syllabus Document Upload */}
        <div>
          <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
            Syllabus / Textbook Material (PDF / MD / TXT)
          </label>
          <div className="relative border-2 border-dashed border-slate-800 hover:border-indigo-500/50 rounded-xl p-4 transition text-center bg-slate-950/40">
            <input
              type="file"
              accept=".pdf,.md,.txt"
              onChange={handleFileChange}
              disabled={isProcessing}
              className="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:cursor-not-allowed"
            />
            <div className="flex flex-col items-center justify-center gap-2">
              <div className="p-2.5 rounded-full bg-slate-800 text-indigo-400">
                <Upload className="w-5 h-5" />
              </div>
              <p className="text-xs font-medium text-slate-300">
                {file ? (
                  <span className="font-semibold text-indigo-300">
                    {file.name} ({formatBytes(file.size)})
                  </span>
                ) : (
                  'Click or drag PDF textbook to upload'
                )}
              </p>
              <p className="text-[11px] text-slate-500">Supports PDF, MD, or TXT curriculum units (up to 200MB)</p>
            </div>
          </div>

          {/* Job Ingestion Status & Progress Display */}
          {isProcessing && (
            <div className="mt-3 p-3.5 rounded-xl bg-indigo-950/40 border border-indigo-500/30 space-y-2.5">
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-indigo-300 flex items-center gap-2">
                  <div className="w-3.5 h-3.5 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
                  {jobStatus.stage || 'Processing document...'}
                </span>
                <span className="font-mono text-indigo-400 font-bold">{jobStatus.progress || 0}%</span>
              </div>

              {/* Progress Bar */}
              <div className="w-full bg-slate-900 rounded-full h-2 overflow-hidden border border-slate-800">
                <div 
                  className="bg-gradient-to-r from-indigo-500 to-violet-500 h-full transition-all duration-300 rounded-full"
                  style={{ width: `${Math.max(jobStatus.progress || 0, 5)}%` }}
                />
              </div>

              <div className="flex justify-between items-center text-[11px] text-slate-400 font-mono">
                <span>Job Status: <strong className="text-indigo-300 uppercase">{jobStatus.status}</strong></span>
                {jobStatus.filename && <span>{jobStatus.filename}</span>}
              </div>
            </div>
          )}

          {isCompleted && (
            <div className="mt-3 p-3 rounded-xl bg-emerald-950/40 border border-emerald-500/30 flex items-center justify-between text-xs text-emerald-400">
              <div className="flex items-center gap-2">
                <Check className="w-4 h-4 flex-shrink-0 text-emerald-400" />
                <div>
                  <span className="font-semibold block text-emerald-300">Textbook Ingested Successfully</span>
                  <span className="text-[11px] text-emerald-400/80">
                    Stored {jobStatus.chunks_added || totalChunksCount} unique semantic chunks in vector database.
                  </span>
                </div>
              </div>
            </div>
          )}

          {!isCompleted && !isProcessing && totalChunksCount > 0 && (
            <div className="mt-2.5 p-2.5 rounded-lg bg-indigo-950/30 border border-indigo-500/20 flex items-center gap-2 text-xs text-indigo-300">
              <Check className="w-4 h-4 flex-shrink-0 text-indigo-400" />
              <span>Vector database contains <strong>{totalChunksCount} chunks</strong> ready for paper generation.</span>
            </div>
          )}

          {isFailed && (
            <div className="mt-3 p-3.5 rounded-xl bg-rose-950/50 border border-rose-500/30 space-y-2">
              <div className="flex items-start gap-2 text-xs text-rose-300">
                <AlertCircle className="w-4 h-4 flex-shrink-0 text-rose-400 mt-0.5" />
                <div className="flex-1">
                  <span className="font-semibold block text-rose-200">Ingestion Failed</span>
                  <p className="text-[11px] text-rose-300/90 font-mono mt-0.5 leading-relaxed bg-slate-950/60 p-2 rounded-lg border border-rose-500/20">
                    {jobStatus.error || 'An unexpected error occurred during processing.'}
                  </p>
                </div>
              </div>

              <div className="pt-1 flex justify-end">
                <button
                  type="button"
                  onClick={handleRetry}
                  className="px-3 py-1.5 rounded-lg bg-rose-900/40 hover:bg-rose-900/60 text-rose-200 text-xs font-semibold flex items-center gap-1.5 border border-rose-500/40 transition"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span>Retry Ingestion</span>
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Topics & Concepts */}
        <div>
          <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
            Target Concepts / Vocabulary (Comma-separated)
          </label>
          <textarea
            rows={2}
            value={concepts}
            onChange={(e) => setConcepts(e.target.value)}
            placeholder="e.g. Arrays, Stacks, Binary Search Trees"
            className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs font-mono text-slate-200 placeholder-slate-600 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition"
          />
        </div>

        {/* Grid: Num Questions & Marks Per Question */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
              Number of Questions
            </label>
            <input
              type="number"
              min={1}
              max={20}
              value={numQuestions}
              onChange={(e) => setNumQuestions(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
              Marks Per Question
            </label>
            <input
              type="number"
              min={1}
              max={100}
              value={marksPerQuestion}
              onChange={(e) => setMarksPerQuestion(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
            />
          </div>
        </div>

        {/* Question Type & Difficulty */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
              Question Type
            </label>
            <select
              value={questionType}
              onChange={(e) => setQuestionType(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500"
            >
              <option value="Descriptive">Descriptive</option>
              <option value="Short Answer">Short Answer</option>
              <option value="Multiple Choice">Multiple Choice</option>
              <option value="Mixed">Mixed Types</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
              Target Difficulty
            </label>
            <select
              value={difficulty}
              onChange={(e) => setDifficulty(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500"
            >
              <option value="Auto">Auto (Derived)</option>
              <option value="Easy">Easy</option>
              <option value="Medium">Medium</option>
              <option value="Hard">Hard</option>
            </select>
          </div>
        </div>

        {/* Bloom's Taxonomy Levels Multi-Select */}
        <div>
          <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
            Target Bloom's Taxonomy Levels
          </label>
          <div className="grid grid-cols-3 gap-2">
            {BLOOM_OPTIONS.map((opt) => {
              const active = selectedBloom.includes(opt.id);
              return (
                <button
                  type="button"
                  key={opt.id}
                  onClick={() => handleBloomToggle(opt.id)}
                  className={`px-3 py-2 rounded-xl text-xs font-medium transition flex items-center justify-between border ${
                    active 
                      ? opt.color + ' ring-1 ring-indigo-500/50' 
                      : 'bg-slate-950 text-slate-400 border-slate-800 hover:border-slate-700'
                  }`}
                >
                  <span>{opt.label}</span>
                  {active && <CheckSquare className="w-3.5 h-3.5 text-indigo-400" />}
                </button>
              );
            })}
          </div>
        </div>

        {/* Submit Action Button */}
        <button
          type="submit"
          disabled={loading || isProcessing || (!ingestionReady && totalChunksCount === 0)}
          title={!ingestionReady && totalChunksCount === 0 ? "Please upload and ingest a textbook first" : ""}
          className="w-full mt-2 py-3.5 px-4 rounded-xl bg-gradient-to-r from-indigo-600 via-indigo-500 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white font-semibold text-sm shadow-lg shadow-indigo-500/25 flex items-center justify-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed transition ring-1 ring-white/10"
        >
          {loading ? (
            <>
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              <span>Executing Agentic Pipeline...</span>
            </>
          ) : isProcessing ? (
            <>
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              <span>Ingesting Textbook...</span>
            </>
          ) : (
            <>
              <Sparkles className="w-4 h-4 text-indigo-200" />
              <span>Generate Question Paper</span>
            </>
          )}
        </button>

        {!ingestionReady && totalChunksCount === 0 && !isProcessing && (
          <p className="text-[11px] text-amber-400/90 text-center font-medium bg-amber-950/30 p-2 rounded-lg border border-amber-500/20">
            ⚠️ Please upload and ingest a syllabus textbook PDF above to enable paper generation.
          </p>
        )}
      </form>
    </div>
  );
}
