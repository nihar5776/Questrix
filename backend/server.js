import express from 'express';
import cors from 'cors';
import multer from 'multer';

const app = express();
const PORT = process.env.PORT || 5000;
const AI_SERVICE_URL = process.env.AI_SERVICE_URL || 'http://127.0.0.1:8000';
const MAX_FILE_SIZE_MB = parseInt(process.env.MAX_FILE_SIZE_MB || '200', 10);

app.use(cors());
app.use(express.json({ limit: '50mb' }));

// Configure Multer storage (in-memory for clean stream forwarding)
const upload = multer({
  storage: multer.memoryStorage(),
  limits: {
    fileSize: MAX_FILE_SIZE_MB * 1024 * 1024 // e.g. 200MB
  }
});

// Helper for allowed extensions
const ALLOWED_EXTENSIONS = ['.pdf', '.txt', '.md'];

function isValidFile(file) {
  if (!file) return false;
  const originalName = file.originalname || '';
  const lowerName = originalName.toLowerCase();
  return ALLOWED_EXTENSIONS.some(ext => lowerName.endsWith(ext));
}

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

// Asynchronous Document Ingestion Start Route
app.post('/api/ingest', (req, res, next) => {
  upload.single('file')(req, res, (err) => {
    if (err instanceof multer.MulterError) {
      if (err.code === 'LIMIT_FILE_SIZE') {
        return res.status(400).json({ error: `File size exceeds the limit of ${MAX_FILE_SIZE_MB}MB.` });
      }
      return res.status(400).json({ error: `Upload error: ${err.message}` });
    } else if (err) {
      return res.status(500).json({ error: `Upload server error: ${err.message}` });
    }
    next();
  });
}, async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: 'No file uploaded.' });
    }

    if (!isValidFile(req.file)) {
      return res.status(400).json({ 
        error: `Unsupported file type "${req.file.originalname}". Only PDF, TXT, and Markdown (.md) files are supported.` 
      });
    }

    const concepts = req.body.concepts || '';
    
    // Construct FormData with Blob
    const fileBlob = new Blob([req.file.buffer], { 
      type: req.file.mimetype || 'application/pdf' 
    });
    
    const formData = new FormData();
    formData.append('file', fileBlob, req.file.originalname);
    formData.append('concepts', concepts);

    // Call Python FastAPI async /ingest endpoint
    const response = await fetch(`${AI_SERVICE_URL}/ingest`, {
      method: 'POST',
      body: formData
    });

    if (!response.ok) {
      const errText = await response.text();
      throw new Error(`AI Service error (${response.status}): ${errText}`);
    }

    const result = await response.json();
    res.json({
      success: true,
      job_id: result.job_id,
      status: result.status,
      message: result.message,
      filename: result.filename,
      filesize: result.filesize
    });

  } catch (error) {
    console.error('Ingest proxy error:', error);
    res.status(500).json({ error: error.message || 'Failed to initiate document ingestion' });
  }
});

// Poll Job Status Route
app.get('/api/ingest/status/:job_id', async (req, res) => {
  try {
    const { job_id } = req.params;
    const response = await fetch(`${AI_SERVICE_URL}/ingest/job/${job_id}`);
    
    if (!response.ok) {
      if (response.status === 404) {
        return res.status(404).json({ error: `Job ${job_id} not found.` });
      }
      const errText = await response.text();
      throw new Error(`AI Service returned ${response.status}: ${errText}`);
    }

    const jobData = await response.json();
    res.json(jobData);
  } catch (error) {
    res.status(500).json({ error: error.message || 'Failed to fetch job status' });
  }
});

// Latest Ingestion Readiness Route
app.get('/api/ingest/latest', async (req, res) => {
  try {
    const response = await fetch(`${AI_SERVICE_URL}/ingest/status`);
    if (!response.ok) {
      throw new Error(`AI Service returned ${response.status}`);
    }
    const data = await response.json();
    res.json(data);
  } catch (error) {
    res.status(500).json({ error: error.message || 'Failed to fetch latest status' });
  }
});

// Question Generation Route
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
      concepts: Array.isArray(concepts) ? concepts : (concepts ? concepts.split(',').map(c => c.trim()) : null),
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
      let errObj;
      try { errObj = JSON.parse(errText); } catch(e) {}
      const msg = errObj?.detail || errText;
      throw new Error(msg);
    }

    const data = await response.json();

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

// Difficulty Calibration Route
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
  console.log(`📦 Max File Upload Limit: ${MAX_FILE_SIZE_MB}MB`);
});
