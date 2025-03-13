import { Router } from 'express';
import { writeFileSync, existsSync, statSync, createReadStream } from 'fs';
import { join } from 'path';
import multer, { memoryStorage } from 'multer';
import { createClient } from 'redis';
import { promisify } from 'util';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const router = Router();
const redisClient = createClient({ url: `redis://${process.env.REDIS_HOST || 'localhost'}:6379` });
const getAsync = promisify(redisClient.get).bind(redisClient);
const setAsync = promisify(redisClient.set).bind(redisClient);

const storage = memoryStorage();
const upload = multer({
  storage: storage,
  limits: { fileSize: 10 * 1024 * 1024 },
  fileFilter: (req, file, cb) => {
    if (file.mimetype.startsWith('video/')) {
      cb(null, true);
    } else {
      cb(new Error('Arquivo não é um video'), false);
    }
  }
});

router.post('/upload/video', upload.single('video'), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).send('Arquivo inválido ou não enviado.');
    }
    const file = req.file;
    const fileName = file.originalname;
    const savePath = join(__dirname, '..', 'uploads', fileName);

    writeFileSync(savePath, file.buffer);
    console.log(`Arquivo salvo em disco: ${savePath}`);

    await setAsync(fileName, file.buffer, 'EX', 60);
    console.log(`Arquivo ${fileName} armazenado no cache Redis por 60s.`);

    return res.sendStatus(204);
  } catch (err) {
    console.error('Erro no upload:', err.message);
    return res.status(400).send('Falha no upload: ' + err.message);
  }
});

router.get('/static/video/:filename', async (req, res) => {
  const fileName = req.params.filename;
  const range = req.headers.range;
  try {
    let fileBuffer = await getAsync(fileName);
    if (fileBuffer) {
      fileBuffer = Buffer.from(fileBuffer);
      const fileSize = fileBuffer.length;
      console.log(`Cache hit para ${fileName} - tamanho ${fileSize} bytes`);
      return streamVideo(res, fileBuffer, fileSize, range);
    }

    const filePath = join(__dirname, '..', 'uploads', fileName);
    if (!existsSync(filePath)) {
      return res.sendStatus(404);
    }
    const stat = statSync(filePath);
    const fileSize = stat.size;
    const fileStream = createReadStream(filePath);
    fileStream.on('data', async (chunk) => {
      await setAsync(fileName, chunk, 'EX', 60);
    });
    return streamVideo(res, fileStream, fileSize, range);
  } catch (err) {
    console.error('Erro no streaming:', err);
    res.status(500).send('Erro no servidor ao enviar vídeo.');
  }
});

function streamVideo(res, videoStream, fileSize, range) {
  if (range) {
    const [startStr, endStr] = range.replace(/bytes=/, '').split('-');
    const start = parseInt(startStr, 10);
    const end = endStr ? parseInt(endStr, 10) : fileSize - 1;
    const chunkSize = (end - start) + 1;
    res.writeHead(206, {
      'Content-Range': `bytes ${start}-${end}/${fileSize}`,
      'Accept-Ranges': 'bytes',
      'Content-Length': chunkSize,
      'Content-Type': 'video/mp4'
    });
    videoStream.pipe(res);
  } else {
    res.writeHead(200, {
      'Content-Length': fileSize,
      'Content-Type': 'video/mp4'
    });
    videoStream.pipe(res);
  }
}

export default router;