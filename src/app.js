import express from 'express'
import uploadRoute from './routes/upload.js'
import streamRoute from './routes/stream.js'

const app = express()

app.use('/upload', uploadRoute)
app.use('/static', streamRoute)

const PORT = process.env.PORT || 3000
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`)
})