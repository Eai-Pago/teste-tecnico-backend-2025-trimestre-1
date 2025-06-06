import express from 'express';
import dotenv from 'dotenv';
import path from 'path';
import uploadRoutes from './routes/upload.js';
import streamRoutes from './routes/stream.js';

dotenv.config();

const app = express();

app.use(express.json());

if (!process.env.VIDEO_STORAGE_PATH) {
  process.env.VIDEO_STORAGE_PATH = path.join(process.cwd(), 'videos');
}

app.use('/upload', uploadRoutes);
app.use('/static', streamRoutes);

app.get('/', (req, res) => {
  res.send('API de Upload e Streaming de Vídeos rodando!');
});

export default app;