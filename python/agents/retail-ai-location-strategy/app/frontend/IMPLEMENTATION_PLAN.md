# AG-UI Integration Implementation Plan

## Overview

Integrate AG-UI (Agent-User Interaction Protocol) with the Retail AI Location Strategy ADK agent to provide a rich, interactive frontend with real-time pipeline visualization and generative UI.

**Key Principle**: The frontend wraps the existing ADK agent without modifying any core agent files. All sub-agents, tools, callbacks, and schemas remain unchanged.

---

## Verified Package Versions (December 2025)

### Python Backend
| Package | Version | Purpose |
|---------|---------|---------|
| `adk-agui-middleware` | latest | TrendMicro middleware (ADKAgent, add_adk_fastapi_endpoint) |
| `fastapi` | >=0.115.0 | Web framework |
| `uvicorn` | >=0.32.0 | ASGI server |
| `google-adk` | >=1.20.0 | Already in project |

### Node.js Frontend
| Package | Version | Purpose |
|---------|---------|---------|
| `@copilotkit/react-core` | ^1.10.6 | CopilotKit React hooks |
| `@copilotkit/react-ui` | ^1.10.6 | CopilotSidebar, chat UI |
| `@ag-ui/core` | ^0.0.41 | AG-UI type definitions |
| `next` | ^14.2.0 | React framework |
| `tailwindcss` | ^3.4.0 | Styling |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (Next.js)                       │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │ CopilotSidebar│  │  useCoAgent  │  │ useCoAgentStateRender │  │
│  │   (Chat UI)   │  │ (Shared State)│  │   (Generative UI)    │  │
│  └──────────────┘  └──────────────┘  └───────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                    AG-UI Protocol (SSE Events)
                    STATE_SNAPSHOT, STATE_DELTA
                              │
┌─────────────────────────────────────────────────────────────────┐
│                    Backend (FastAPI + ADK)                       │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                 ADKAgent Middleware                         │ │
│  │  (adk_middleware.ADKAgent + add_adk_fastapi_endpoint)      │ │
│  └────────────────────────────────────────────────────────────┘ │
│                              │                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │          UNCHANGED: root_agent (SequentialAgent)           │ │
│  │  IntakeAgent → MarketResearch → CompetitorMapping →        │ │
│  │  GapAnalysis → StrategyAdvisor → ReportGenerator →         │ │
│  │  InfographicGenerator                                       │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## State Fields Exposed to Frontend

These state fields are already set by existing callbacks in `callbacks/pipeline_callbacks.py`:

| State Field | Type | Set By | Description |
|-------------|------|--------|-------------|
| `pipeline_stage` | string | before_* callbacks | Current stage ID |
| `stages_completed` | string[] | after_* callbacks | Completed stage IDs |
| `target_location` | string | IntakeAgent | User's target location |
| `business_type` | string | IntakeAgent | Type of business |
| `strategic_report` | LocationIntelligenceReport | StrategyAdvisorAgent | Full analysis report |
| `market_research_findings` | string | MarketResearchAgent | Research text |
| `competitor_analysis` | string | CompetitorMappingAgent | Competitor text |
| `gap_analysis` | string | GapAnalysisAgent | Gap analysis text |

The ADKAgent middleware automatically emits these as `STATE_SNAPSHOT` and `STATE_DELTA` events.

---

## Task Checklist

### Phase 1: Backend Setup
- [ ] Create `frontend/backend/` directory
- [ ] Create `frontend/backend/main.py` with FastAPI + ADKAgent wrapper
- [ ] Create `frontend/backend/requirements.txt` with dependencies
- [ ] Test backend starts and responds to AG-UI events

### Phase 2: Frontend Scaffolding
- [ ] Create `frontend/` Next.js project (manual or npx create-ag-ui-app)
- [ ] Install CopilotKit and AG-UI packages
- [ ] Configure Tailwind CSS
- [ ] Create `.env.local` with backend URL

### Phase 3: CopilotKit Integration
- [ ] Create `app/layout.tsx` with CopilotKit provider
- [ ] Create `app/page.tsx` with CopilotSidebar
- [ ] Verify connection to backend

### Phase 4: TypeScript Types
- [ ] Create `lib/types.ts` matching Pydantic schemas exactly
- [ ] Export all types for components

### Phase 5: Generative UI Components
- [ ] Create `components/PipelineProgress.tsx` - 7-stage tracker
- [ ] Create `components/LocationReport.tsx` - Main recommendation card
- [ ] Create `components/CompetitorCard.tsx` - Competition stats
- [ ] Create `components/MarketCard.tsx` - Market characteristics
- [ ] Create `components/ArtifactViewer.tsx` - Report/infographic viewer
- [ ] Create `components/ToolCallVisualizer.tsx` - Tool call hooks

### Phase 6: Integration & Testing
- [ ] Wire up useCoAgent and useCoAgentStateRender
- [ ] Test full pipeline flow with sample query
- [ ] Verify all state updates render correctly
- [ ] Test artifact viewing (HTML report, infographic)

### Phase 7: Documentation
- [ ] Create `frontend/README.md` with setup instructions
- [ ] Document environment variables
- [ ] Add troubleshooting section

---

## File Structure

```
retail_ai_location_strategy_adk/
├── agent.py                    # UNCHANGED
├── sub_agents/                 # UNCHANGED
├── tools/                      # UNCHANGED
├── schemas/                    # UNCHANGED
├── callbacks/                  # UNCHANGED
├── config.py                   # UNCHANGED
│
└── frontend/                   # NEW: AG-UI Frontend
    ├── IMPLEMENTATION_PLAN.md  # This plan (for context)
    ├── README.md               # Setup instructions
    │
    ├── backend/
    │   ├── main.py             # FastAPI + ADKAgent wrapper
    │   └── requirements.txt    # Backend dependencies
    │
    ├── package.json
    ├── next.config.js
    ├── tailwind.config.js
    ├── tsconfig.json
    ├── .env.local.example
    │
    ├── app/
    │   ├── layout.tsx          # CopilotKit provider
    │   ├── page.tsx            # Main page with sidebar
    │   └── globals.css         # Tailwind imports
    │
    ├── components/
    │   ├── PipelineProgress.tsx
    │   ├── LocationReport.tsx
    │   ├── CompetitorCard.tsx
    │   ├── MarketCard.tsx
    │   ├── ArtifactViewer.tsx
    │   └── ToolCallVisualizer.tsx
    │
    └── lib/
        └── types.ts            # TypeScript types
```

---

## Implementation Details

### 1. Backend: `frontend/backend/main.py`

```python
"""FastAPI server wrapping ADK agent with AG-UI middleware."""

import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from adk_middleware import ADKAgent, add_adk_fastapi_endpoint

# Import the EXISTING root_agent - no modifications needed
from retail_ai_location_strategy_adk.agent import root_agent

# Wrap with AG-UI middleware
adk_agent = ADKAgent(
    adk_agent=root_agent,
    app_name="retail_location_strategy",
    user_id="demo_user",
)

# Create FastAPI app
app = FastAPI(title="Retail Location Strategy API")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add AG-UI endpoint at root
add_adk_fastapi_endpoint(app, adk_agent, path="/")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### 2. Backend: `frontend/backend/requirements.txt`

```
adk-agui-middleware
fastapi>=0.115.0
uvicorn>=0.32.0
```

### 3. Frontend: `lib/types.ts`

Must match Pydantic schemas in `schemas/report_schema.py` exactly:

```typescript
// Matches schemas/report_schema.py exactly

export interface StrengthAnalysis {
  factor: string;
  description: string;
  evidence_from_analysis: string;
}

export interface ConcernAnalysis {
  risk: string;
  description: string;
  mitigation_strategy: string;
}

export interface CompetitionProfile {
  total_competitors: number;
  density_per_km2: number;
  chain_dominance_pct: number;
  avg_competitor_rating: number;
  high_performers_count: number;
}

export interface MarketCharacteristics {
  population_density: string;  // "Low" | "Medium" | "High"
  income_level: string;
  infrastructure_access: string;
  foot_traffic_pattern: string;
  rental_cost_tier: string;
}

export interface LocationRecommendation {
  location_name: string;
  area: string;
  overall_score: number;  // 0-100
  opportunity_type: string;
  strengths: StrengthAnalysis[];
  concerns: ConcernAnalysis[];
  competition: CompetitionProfile;
  market: MarketCharacteristics;
  best_customer_segment: string;
  estimated_foot_traffic: string;
  next_steps: string[];
}

export interface AlternativeLocation {
  location_name: string;
  area: string;
  overall_score: number;
  opportunity_type: string;
  key_strength: string;
  key_concern: string;
  why_not_top: string;
}

export interface LocationIntelligenceReport {
  target_location: string;
  business_type: string;
  analysis_date: string;
  market_validation: string;
  total_competitors_found: number;
  zones_analyzed: number;
  top_recommendation: LocationRecommendation;
  alternative_locations: AlternativeLocation[];
  key_insights: string[];
  methodology_summary: string;
}

// Agent state type for useCoAgent
export interface AgentState {
  // Pipeline tracking (from callbacks)
  pipeline_stage: string;
  stages_completed: string[];
  pipeline_start_time?: string;

  // User request (from IntakeAgent)
  target_location: string;
  business_type: string;
  additional_context?: string;

  // Analysis results
  market_research_findings?: string;
  competitor_analysis?: string;
  gap_analysis?: string;
  strategic_report?: LocationIntelligenceReport;

  // Metadata
  current_date?: string;
}
```

### 4. Frontend: `app/layout.tsx`

```tsx
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { CopilotKit } from "@copilotkit/react-core";
import "@copilotkit/react-ui/styles.css";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Retail AI Location Strategy",
  description: "AI-powered retail site selection with Google ADK",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <CopilotKit
          runtimeUrl={process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000"}
          agent="LocationStrategyPipeline"
        >
          {children}
        </CopilotKit>
      </body>
    </html>
  );
}
```

### 5. Frontend: `app/page.tsx`

```tsx
"use client";

import { CopilotSidebar } from "@copilotkit/react-ui";
import { useCoAgent, useCoAgentStateRender } from "@copilotkit/react-core";
import { PipelineProgress } from "@/components/PipelineProgress";
import { LocationReport } from "@/components/LocationReport";
import { CompetitorCard } from "@/components/CompetitorCard";
import { MarketCard } from "@/components/MarketCard";
import type { AgentState } from "@/lib/types";

export default function Home() {
  // Connect to agent state
  const { state } = useCoAgent<AgentState>({
    name: "LocationStrategyPipeline",
  });

  // Render state in chat as generative UI
  useCoAgentStateRender<AgentState>({
    name: "LocationStrategyPipeline",
    render: ({ state }) => {
      if (!state) return null;

      return (
        <div className="space-y-4">
          {/* Always show pipeline progress */}
          <PipelineProgress
            currentStage={state.pipeline_stage}
            completedStages={state.stages_completed || []}
          />

          {/* Show report when available */}
          {state.strategic_report && (
            <>
              <LocationReport report={state.strategic_report} />
              <div className="grid grid-cols-2 gap-4">
                <CompetitorCard
                  competition={state.strategic_report.top_recommendation.competition}
                />
                <MarketCard
                  market={state.strategic_report.top_recommendation.market}
                />
              </div>
            </>
          )}
        </div>
      );
    },
  });

  return (
    <CopilotSidebar
      defaultOpen={true}
      clickOutsideToClose={false}
      labels={{
        title: "Retail Location Strategy",
        initial: "Hi! Tell me where you want to open your business and I'll analyze the location for you.\n\nExamples:\n- \"I want to open a coffee shop in Indiranagar, Bangalore\"\n- \"Analyze Austin, Texas for a fitness studio\"\n- \"Where should I open a bakery in Dubai Marina?\"",
      }}
    >
      <main className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 p-8">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">
            Retail AI Location Strategy
          </h1>
          <p className="text-gray-600 mb-8">
            Powered by Google ADK + Gemini 3
          </p>

          {/* Current analysis status */}
          {state?.target_location && (
            <div className="bg-white rounded-xl shadow-sm border p-6 mb-8">
              <div className="flex items-center gap-4">
                <div className="h-12 w-12 bg-blue-100 rounded-full flex items-center justify-center">
                  <span className="text-2xl">📍</span>
                </div>
                <div>
                  <h2 className="text-xl font-semibold">
                    {state.business_type}
                  </h2>
                  <p className="text-gray-600">{state.target_location}</p>
                </div>
                <div className="ml-auto">
                  <span className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm font-medium">
                    {state.pipeline_stage?.replace(/_/g, " ") || "Ready"}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Pipeline Progress outside chat */}
          {state?.stages_completed && state.stages_completed.length > 0 && (
            <div className="mb-8">
              <PipelineProgress
                currentStage={state.pipeline_stage}
                completedStages={state.stages_completed}
              />
            </div>
          )}

          {/* Final Report Card */}
          {state?.strategic_report && (
            <div className="space-y-6">
              <LocationReport report={state.strategic_report} />
              <div className="grid md:grid-cols-2 gap-6">
                <CompetitorCard
                  competition={state.strategic_report.top_recommendation.competition}
                />
                <MarketCard
                  market={state.strategic_report.top_recommendation.market}
                />
              </div>
            </div>
          )}

          {/* Welcome state */}
          {!state?.target_location && (
            <div className="bg-white rounded-xl shadow-sm border p-8 text-center">
              <div className="text-6xl mb-4">🏪</div>
              <h2 className="text-2xl font-semibold mb-2">
                Find Your Perfect Location
              </h2>
              <p className="text-gray-600 max-w-md mx-auto">
                Tell me where you want to open your business in the chat,
                and I'll analyze the market, competition, and provide
                strategic recommendations.
              </p>
            </div>
          )}
        </div>
      </main>
    </CopilotSidebar>
  );
}
```

### 6. Component: `components/PipelineProgress.tsx`

```tsx
interface PipelineProgressProps {
  currentStage: string;
  completedStages: string[];
}

const STAGES = [
  { id: "intake", label: "Parsing Request", icon: "📝" },
  { id: "market_research", label: "Market Research", icon: "🔍" },
  { id: "competitor_mapping", label: "Competitor Mapping", icon: "📍" },
  { id: "gap_analysis", label: "Gap Analysis", icon: "📊" },
  { id: "strategy_synthesis", label: "Strategy Synthesis", icon: "🧠" },
  { id: "report_generation", label: "Report Generation", icon: "📄" },
  { id: "infographic_generation", label: "Infographic", icon: "🎨" },
];

export function PipelineProgress({ currentStage, completedStages }: PipelineProgressProps) {
  return (
    <div className="bg-white rounded-xl shadow-sm border p-4">
      <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
        <span>Pipeline Progress</span>
        <span className="text-sm font-normal text-gray-500">
          ({completedStages.length}/{STAGES.length} complete)
        </span>
      </h3>
      <div className="space-y-2">
        {STAGES.map((stage) => {
          const isComplete = completedStages.includes(stage.id);
          const isCurrent = currentStage === stage.id;

          return (
            <div
              key={stage.id}
              className={`flex items-center gap-3 p-3 rounded-lg transition-all ${
                isComplete
                  ? "bg-green-50 border border-green-200"
                  : isCurrent
                  ? "bg-amber-50 border border-amber-200 animate-pulse"
                  : "bg-gray-50 border border-gray-100"
              }`}
            >
              <span className="text-xl">
                {isComplete ? "✅" : isCurrent ? "⏳" : stage.icon}
              </span>
              <span
                className={`font-medium ${
                  isComplete
                    ? "text-green-700"
                    : isCurrent
                    ? "text-amber-700"
                    : "text-gray-500"
                }`}
              >
                {stage.label}
              </span>
              {isCurrent && (
                <span className="ml-auto text-xs text-amber-600 font-medium">
                  In Progress...
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

---

## Running the Application

### Terminal 1: Backend
```bash
cd retail_ai_location_strategy_adk/frontend/backend
pip install -r requirements.txt
python main.py
# Server runs at http://localhost:8000
```

### Terminal 2: Frontend
```bash
cd retail_ai_location_strategy_adk/frontend
npm install
npm run dev
# App runs at http://localhost:3000
```

### Terminal 3 (Optional): Original ADK Web UI
```bash
cd build-with-adk
adk web
# Original UI at http://localhost:8080
```

---

## Critical Files (Read-Only Reference)

These existing files inform the implementation but should NOT be modified:

| File | Purpose |
|------|---------|
| `agent.py` | root_agent definition (SequentialAgent) |
| `sub_agents/__init__.py` | Exports all 7 sub-agents |
| `schemas/report_schema.py` | LocationIntelligenceReport Pydantic model |
| `callbacks/pipeline_callbacks.py` | State updates (pipeline_stage, stages_completed) |
| `config.py` | Model configuration |
| `tools/__init__.py` | Exports tools (search_places, generate_infographic, generate_html_report) |

---

## Sources

- [AG-UI Protocol Docs](https://docs.ag-ui.com/)
- [CopilotKit ADK Docs](https://docs.copilotkit.ai/adk)
- [adk-agui-middleware GitHub](https://github.com/trendmicro/adk-agui-middleware)
- [Google ADK AG-UI Integration](https://google.github.io/adk-docs/tools/third-party/ag-ui/)
- [AG-UI GitHub](https://github.com/ag-ui-protocol/ag-ui)
- [CopilotKit npm](https://www.npmjs.com/package/@copilotkit/react-core)
