# CORS Issue Fixed - LLM Calls Now Through Backend

## Problem
The frontend was calling OpenAI API directly from the browser, which caused CORS (Cross-Origin Resource Sharing) errors:
```
Access to fetch at 'https://api.openai.com/v1/chat/completions' from origin 'http://localhost:3000' 
has been blocked by CORS policy: Response to preflight request doesn't pass access control check: 
No 'Access-Control-Allow-Origin' header is present on the requested resource.
```

## Solution
Created a backend proxy endpoint for LLM calls to avoid CORS restrictions.

### Backend Changes

#### 1. Added OpenAI to Requirements
**File:** `backend/requirements.txt`
```
openai==1.*
```

#### 2. Added OpenAI Client and Endpoint
**File:** `backend/main.py`

Added imports:
```python
from openai import OpenAI

# Initialize OpenAI client
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
```

Added new endpoint:
```python
class LLMRequest(BaseModel):
    messages: List[Dict[str, str]]
    model: str = "gpt-4o-mini"
    temperature: float = 0.7

@app.post("/llm_chat")
async def llm_chat(request: LLMRequest):
    """
    Proxy endpoint for OpenAI chat completions to avoid CORS issues.
    """
    try:
        completion = openai_client.chat.completions.create(
            model=request.model,
            messages=request.messages,
            temperature=request.temperature
        )
        
        return {
            "content": completion.choices[0].message.content,
            "model": completion.model,
            "usage": {
                "prompt_tokens": completion.usage.prompt_tokens,
                "completion_tokens": completion.usage.completion_tokens,
                "total_tokens": completion.usage.total_tokens
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM error: {str(e)}")
```

### Frontend Changes

#### 1. Removed Direct OpenAI Import
**File:** `frontend/app/page.tsx`

Removed:
```typescript
import OpenAI from "openai";
```

#### 2. Added Helper Function
Created `callLLM()` helper that calls the backend endpoint:
```typescript
async function callLLM(
  messages: { role: string; content: string }[], 
  temperature: number = 0.7, 
  model: string = "gpt-4o-mini"
): Promise<string> {
  try {
    const response = await fetch("http://localhost:8000/llm_chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages, temperature, model }),
    });
    
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || "LLM call failed");
    }
    
    const data = await response.json();
    return data.content;
  } catch (error) {
    console.error("LLM call error:", error);
    throw error;
  }
}
```

#### 3. Replaced All OpenAI Direct Calls
Replaced **4 instances** of direct OpenAI API calls:

**Before:**
```typescript
const openai = new OpenAI({
  apiKey: process.env.NEXT_PUBLIC_OPENAI_API_KEY!,
  dangerouslyAllowBrowser: true,
});

const completion = await openai.chat.completions.create({
  model: "gpt-4o-mini",
  messages: [...],
  temperature: 0.7,
});

const reply = completion.choices[0]?.message?.content;
```

**After:**
```typescript
const reply = await callLLM([...messages], 0.7);
```

#### 4. Removed API Key Checks
No longer need to check for `NEXT_PUBLIC_OPENAI_API_KEY` in the frontend since the backend handles authentication.

### Additional Fixes

#### TypeScript Typo Fixed
Fixed inconsistent naming in `detectMoveAnalysisRequest`:
- Changed `isMovAnalysis` to `isMoveAnalysis` throughout the function

## Benefits

1. **No More CORS Errors** - All LLM calls go through the backend
2. **Better Security** - API key only stored on backend (`.env`), not exposed to browser
3. **Centralized Control** - Can add rate limiting, logging, or caching at the backend level
4. **Simpler Frontend Code** - No need for `dangerouslyAllowBrowser: true` flag
5. **Consistent Error Handling** - Backend can provide standardized error responses

## Testing

1. Start backend: `cd backend && python3 main.py`
2. Start frontend: `cd frontend && npm run dev`
3. Open http://localhost:3000
4. Test any LLM-powered feature:
   - General chat ("hi", "hello")
   - Position analysis ("analyze this position")
   - Move analysis ("analyze e4")
   - Play mode commentary

All LLM calls should now work without CORS errors! ✅

## API Endpoint Documentation

### POST `/llm_chat`

**Request Body:**
```json
{
  "messages": [
    {"role": "system", "content": "You are a helpful assistant"},
    {"role": "user", "content": "Hello"}
  ],
  "model": "gpt-4o-mini",
  "temperature": 0.7
}
```

**Response:**
```json
{
  "content": "Hello! How can I help you today?",
  "model": "gpt-4o-mini",
  "usage": {
    "prompt_tokens": 20,
    "completion_tokens": 10,
    "total_tokens": 30
  }
}
```

**Error Response:**
```json
{
  "detail": "LLM error: [error message]"
}
```

