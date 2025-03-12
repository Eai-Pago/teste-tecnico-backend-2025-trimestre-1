const express = require('express');
const fs = require('fs');
const path = require('path');
const multer = require('multer');
const redis = require('redis');

const app = express();
const PORT = process.env.PORT || 3000;

app.listen(PORT, () => {
    console.log(`Servidor rodando na porta ${PORT}`);
  });
  