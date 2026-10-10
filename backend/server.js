import express from 'express';
import cors from 'cors';
import multer from 'multer';

const app = express();
const PORT = process.env.PORT || 5000;
const AI_SERVICE_URL = process.env.AI_SERVICE_URL || 'http://127.0.0.1:8000';

app.use(cors());
app.use(express.json());

const upload = multer({ storage: multer.memoryStorage() });

// Health check proxy
app.get('/api/health', async (req, res) => {
  try {
    const response = await fetch(`${AI_SERVICE_URL}/health`);
    if (!response.ok) {
      throw new Error(`AI Service returned ${response.status}`);
    }
    const data = await response.json();
    res.json({
      status: 'ok',
      backend: 'Questrix Node.js API Gateway',
      ai_service: data
    });
  } catch (error) {
    res.status(503).json({
      status: 'error',
      message: 'Python AI Engine is not reachable at ' + AI_SERVICE_URL,
      details: error.message
    });
  }
});

// Document Ingestion route
app.post('/api/ingest', upload.single('file'), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: 'No file uploaded' });
    }

    const concepts = req.body.concepts || '';
    
    // Create a Blob/File from the multer memory buffer to pass to native fetch FormData
    const fileBlob = new Blob([req.file.buffer], { type: req.file.mimetype || 'application/octet-stream' });
    
    const formData = new FormData();
    formData.append('file', fileBlob, req.file.originalname);
    formData.append('concepts', concepts);

    const response = await fetch(`${AI_SERVICE_URL}/ingest`, {
      method: 'POST',
      body: formData
    });

    if (!response.ok) {
      const errText = await response.text();
      throw new Error(`AI Service Ingest Error (${response.status}): ${errText}`);
    }

    const result = await response.json();
    res.json({
      success: true,
      message: `Successfully ingested document with ${result.chunks_added} chunks`,
      chunks_added: result.chunks_added,
      concepts: result.concepts
    });
  } catch (error) {
    console.error('Ingest proxy error:', error);
    res.status(500).json({ error: error.message || 'Failed to ingest syllabus document' });
  }
});

// Question Generation route
app.post('/api/generate', async (req, res) => {
  try {
    const {
      subject = 'General Knowledge',
      num_questions = 6,
      concepts = null,
      bloom_levels = null,
      difficulty = null,
      question_type = 'Descriptive',
      marks_per_question = 5,
      seed = 0
    } = req.body;

    const payload = {
      subject,
      num_questions: parseInt(num_questions, 10),
      concepts: Array.isArray(concepts) ? concepts : (concepts ? concepts.split(',').map(c => c.strip ? c.strip() : c.trim()) : null),
      bloom_levels: Array.isArray(bloom_levels) && bloom_levels.length > 0 ? bloom_levels : null,
      difficulty: difficulty && difficulty !== 'Mixed' && difficulty !== 'Auto' ? difficulty : null,
      question_type,
      seed: seed || Math.floor(Math.random() * 1000)
    };

    const response = await fetch(`${AI_SERVICE_URL}/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      const errText = await response.text();
      throw new Error(`AI Service Generation Error (${response.status}): ${errText}`);
    }

    const data = await response.json();

    // Attach subject and calculated marks to output
    const questionsWithMarks = (data.questions || []).map((q, idx) => ({
      id: idx + 1,
      ...q,
      marks: parseInt(marks_per_question, 10) || 5
    }));

    res.json({
      success: true,
      subject,
      total_questions: questionsWithMarks.length,
      total_marks: questionsWithMarks.reduce((acc, q) => acc + q.marks, 0),
      questions: questionsWithMarks,
      rejected: data.rejected || [],
      summary: data.summary || {},
      trace: data.trace || []
    });
  } catch (error) {
    console.error('Generation proxy error:', error);
    res.status(500).json({ error: error.message || 'Failed to generate question paper' });
  }
});

// Difficulty Calibration route
app.post('/api/calibrate', async (req, res) => {
  try {
    const response = await fetch(`${AI_SERVICE_URL}/calibrate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req.body)
    });
    if (!response.ok) {
      const errText = await response.text();
      throw new Error(`AI Service Calibrate Error (${response.status}): ${errText}`);
    }
    const data = await response.json();
    res.json(data);
  } catch (error) {
    res.status(500).json({ error: error.message || 'Failed to calibrate question paper difficulty' });
  }
});

app.listen(PORT, () => {
  console.log(`🚀 Questrix AI Backend Gateway listening on http://localhost:${PORT}`);
  console.log(`🔗 Connected to AI Service at ${AI_SERVICE_URL}`);
});
