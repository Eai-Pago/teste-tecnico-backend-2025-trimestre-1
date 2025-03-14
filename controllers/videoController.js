import { Router } from 'express';
import { writeFileSync, existsSync, statSync, createReadStream, mkdirSync, readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import multer, { memoryStorage } from 'multer';
import { createClient } from 'redis';

const router = Router();

// Corrige o __dirname para ESM
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Diretório para uploads
const uploadDir = join(__dirname, '..', 'uploads');
if (!existsSync(uploadDir)) {
  mkdirSync(uploadDir);
}

// Cliente Redis
const redisClient = createClient({ url: `redis://${process.env.REDIS_HOST || 'localhost'}:6379` });
redisClient.on('error', (err) => console.error('Redis Client Error:', err));
redisClient.connect();

// Configuração do Multer
const upload = multer({
  storage: memoryStorage(),
  limits: { fileSize: 10 * 1024 * 1024 },
  fileFilter: (req, file, cb) => {
    if (file.mimetype.startsWith('video/')) {
      cb(null, true);
    } else {
      cb(new Error('Arquivo não é um vídeo'), false);
    }
  },
});

router.post('/upload/video', upload.single('video'), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).send('Arquivo inválido ou não enviado.');
    }

    const file = req.file;
    const fileName = file.originalname;
    const savePath = join(uploadDir, fileName);

    writeFileSync(savePath, file.buffer);
    console.log(`Arquivo salvo: ${savePath}`);

    // No Redis, armazenamos só um indicador da existência do arquivo
    await redisClient.set(fileName, "cached", { EX: 60 });

    return res.sendStatus(204);
  } catch (err) {
    console.error('Erro no upload:', err);
    return res.status(500).send('Falha no upload: ' + err.message);
  }
});

router.get('/static/video/:filename', async (req, res) => {
  const fileName = req.params.filename;
  const range = req.headers.range;

  try {
    const filePath = join(uploadDir, fileName);

    // Checagem rápida no Redis (só indicador)
    const cacheExists = await redisClient.get(fileName);
    if (cacheExists) {
      console.log(`Cache HIT (indicador apenas) para ${fileName}`);
    } else {
      console.log(`Cache MISS para ${fileName}`);
    }

    if (!existsSync(filePath)) {
      return res.sendStatus(404);
    }

    const fileSize = statSync(filePath).size;

    if (range) {
      const parts = range.replace(/bytes=/, "").split("-");
      const start = parseInt(parts[0], 10);
      const end = parts[1] ? parseInt(parts[1], 10) : fileSize - 1;
      const chunkSize = (end - start) + 1;
      const fileStream = createReadStream(filePath, { start, end });

      res.writeHead(206, {
        'Content-Range': `bytes ${start}-${end}/${fileSize}`,
        'Accept-Ranges': 'bytes',
        'Content-Length': chunkSize,
        'Content-Type': 'video/mp4'
      });

      fileStream.pipe(res);
    } else {
      res.writeHead(200, {
        'Content-Length': fileSize,
        'Content-Type': 'video/mp4'
      });

      createReadStream(filePath).pipe(res);
    }
  } catch (err) {
    console.error('Erro no streaming:', err);
    res.status(500).send('Erro interno ao enviar vídeo.');
  }
});


export default router;
