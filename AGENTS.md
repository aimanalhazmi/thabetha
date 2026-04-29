<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan:
specs/012-ai-voice-debt-draft/plan.md
<!-- SPECKIT END -->

## Active Technologies
- Python 3.12 backend; TypeScript strict frontend + FastAPI, Pydantic, Supabase/Postgres, Supabase Storage, React, Vite, lucide-react, OpenAI speech-to-text client behind a local provider interface (012-ai-voice-debt-draft)
- Supabase Postgres for usage counters/draft metadata if persisted; private `voice-notes` bucket for temporary audio; in-memory repository equivalents for tests (012-ai-voice-debt-draft)

## Recent Changes
- 012-ai-voice-debt-draft: Added Python 3.12 backend; TypeScript strict frontend + FastAPI, Pydantic, Supabase/Postgres, Supabase Storage, React, Vite, lucide-react, OpenAI speech-to-text client behind a local provider interface
