import express from 'express';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import videoRouter from './controllers/videoController.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const app = express();
const PORT = process.env.PORT || 3000;

app.use('/uploads', express.static(join(__dirname, 'uploads')));

app.use('/api', videoRouter);

app.listen(PORT, () => {
  console.log(`Servidor rodando na porta ${PORT}`);
});