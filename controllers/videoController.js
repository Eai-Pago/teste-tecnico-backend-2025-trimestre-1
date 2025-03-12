app.post('/upload/video', upload.single('video'), async (req, res) => {
    try {
      if (!req.file) {
        return res.status(400).send('Arquivo inválido ou não enviado.');
      }
      const file = req.file;
      const fileName = file.originalname;
  
      const savePath = path.join(__dirname, 'videos', fileName);
      fs.writeFileSync(savePath, file.buffer);
      console.log(`Arquivo salvo em disco: ${savePath}`);
  
      await redisClient.set(fileName, file.buffer, { EX: 60 });
      console.log(`Arquivo ${fileName} armazenado no cache Redis por 60s.`);
  
      return res.sendStatus(204);
    } catch (err) {
      console.error('Erro no upload:', err.message);
      return res.status(400).send('Falha no upload: ' + err.message);
    }
  });
  
app.get('/static/video/:filename', async (req, res) => {
    const fileName = req.params.filename;
    const range = req.headers.range;
    try {
      let fileBuffer = await redisClient.get(fileName);
      if (fileBuffer) {
        fileBuffer = Buffer.from(fileBuffer);
        const fileSize = fileBuffer.length;
        console.log(`Cache hit para ${fileName} - tamanho ${fileSize} bytes`);
        if (range) {
          const [startStr, endStr] = range.replace(/bytes=/, '').split('-');
          const start = parseInt(startStr, 10);
          const end = endStr ? parseInt(endStr, 10) : fileSize - 1;
          const chunkSize = (end - start) + 1;
          const chunk = fileBuffer.slice(start, end + 1);
          res.writeHead(206, {
            'Content-Range': `bytes ${start}-${end}/${fileSize}`,
            'Accept-Ranges': 'bytes',
            'Content-Length': chunkSize,
            'Content-Type': 'video/mp4'
          });
          return res.end(chunk);
        } else {
          res.writeHead(200, {
            'Content-Length': fileSize,
            'Content-Type': 'video/mp4'
          });
          return res.end(fileBuffer);
        }
      }
  
      const filePath = path.join(__dirname, 'videos', fileName);
      if (!fs.existsSync(filePath)) {
        return res.sendStatus(404); 
      }
      const stat = fs.statSync(filePath);
      const fileSize = stat.size;
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
        const fileStream = fs.createReadStream(filePath, { start, end });
        fileStream.pipe(res);
      } else {
        res.writeHead(200, {
          'Content-Length': fileSize,
          'Content-Type': 'video/mp4'
        });
        const fileStream = fs.createReadStream(filePath);
        fileStream.pipe(res);
        const data = fs.readFileSync(filePath);
        await redisClient.set(fileName, data, { EX: 60 });
      }
    } catch (err) {
      console.error('Erro no streaming:', err);
      res.status(500).send('Erro no servidor ao enviar v\u00eddeo.');
    }
  });
  