// Runs a minimal Vercel AI Gateway streaming text request from local Node.js.
import { streamText } from 'ai'

const result = streamText({
  model: 'openai/gpt-5.5',
  prompt: 'Explain quantum computing in simple terms.',
})

for await (const chunk of result.textStream) {
  process.stdout.write(chunk)
}
