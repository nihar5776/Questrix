import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import InputForm from './components/InputForm';
import OutputView from './components/OutputView';
import ValidationAnalytics from './components/ValidationAnalytics';
import { checkHealth, generateQuestionPaper } from './api/client';

export default function App() {
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(false);
  const [outputData, setOutputData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function loadHealth() {
      const res = await checkHealth();
      setHealth(res);
    }
    loadHealth();
    const interval = setInterval(loadHealth, 15000);
    return () => clearInterval(interval);
  }, []);

  const handleGenerate = async (formData) => {
    setLoading(true);
    setError(null);
    try {
      const res = await generateQuestionPaper(formData);
      setOutputData(res);
    } catch (err) {
      setError(err.message || 'Failed to generate question paper. Please check python AI engine status.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-['Plus_Jakarta_Sans',sans-serif]">
      <Header health={health} />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Left Input Form Column */}
          <div className="lg:col-span-5">
            <InputForm onSubmit={handleGenerate} loading={loading} />
          </div>

          {/* Right Output View Column */}
          <div className="lg:col-span-7 space-y-6">
            {outputData && outputData.summary && (
              <ValidationAnalytics summary={outputData.summary} trace={outputData.trace} />
            )}
            <OutputView data={outputData} loading={loading} error={error} />
          </div>
        </div>
      </main>

      <footer className="border-t border-slate-900 py-6 bg-slate-950 text-center text-xs text-slate-500">
        <p>Questrix AI — Powered by Calibrated evidence-Anchored Question Generation (CAL-QG)</p>
      </footer>
    </div>
  );
}
