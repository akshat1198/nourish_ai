# NourishAI 🥗 - Your Smart Recipe Recommender

Turn your random pantry ingredients into delicious meal ideas with NourishAI! This AI-powered recipe recommender helps you discover what to cook based on the ingredients you have, powered by modern language models and smart ingredient matching.

## 🚀 Getting Started

### Backend Setup

1. Create and activate a Python virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```

3. Start the development server:
   ```bash
   cd backend
   uvicorn main:app --reload
   ```

4. Access the API:
   - API Root: http://127.0.0.1:8000/
   - Interactive API Documentation: http://127.0.0.1:8000/docs
   - Alternative API Documentation: http://127.0.0.1:8000/redoc

## 🌟 Key Features

- **Ingredient-Based Recipe Search**: Simply list what's in your fridge and pantry
- **Smart Substitutions**: Automatically suggests ingredient swaps when you're missing items
- **Dietary Customization**: Filter recipes based on preferences (vegetarian, nut-free, etc.)
- **Time-Aware**: Set your maximum cooking time and get suitable recommendations
- **Shopping List Generator**: Auto-generates minimal shopping lists for missing ingredients
- **User-Friendly Interface**: Simple web UI built with Streamlit/Gradio

## 🏗️ Architecture Overview

```
┌────────────────────────┐
│        Frontend        │  React/Next: pantry input, filters,
│  (Web/Mobile UI)       │  dietary prefs, history
└──────────┬─────────────┘
           │ JSON request
           ▼
┌────────────────────────┐
│      API Gateway       │  Auth, rate limit, request schema check
└──────────┬─────────────┘
           │
     ┌─────▼─────────────────────────────────────────────────────────┐
     │                    Orchestrator Service                        │
     │     (decides fast path vs. LLM path; logs everything)          │
     └─────┬───────────────┬─────────────────────────────┬───────────┘
           │               │                             │
           │               │                             │
           │               │                             │
   ┌───────▼──────┐  ┌─────▼─────────────────┐    ┌──────▼─────────┐
   │ Cache Layer  │  │  Retrieval Service    │    │  Rules/Filter  │
   │ (Redis)      │  │  (Vector + SQL search)│    │  Engine        │
   │ key: pantry+ │  │  - Vector DB (FAISS/  │    │  - Diet rules  │
   │ prefs+goal   │  │    pgvector)          │    │  - Allergens   │
   └───────┬──────┘  │  - SQL DB (recipes,   │    │  - Cost/time   │
           │         │    nutrition, tags)   │    └──────┬─────────┘
       hit │ miss    └───────────┬───────────┘           │
           │                     │                       │
           ▼                     │ top-K candidates      │
   ┌─────────────────┐           │                       │
   │ Return cached   │◄──────────┘                       │
   │ result fast     │                                   │
   └─────────────────┘                                   │
                                                         │
                                                         ▼
                                            ┌──────────────────────────┐
                                            │  Validation Services     │
                                            │  - Nutrition API check   │
                                            │  - Units/steps checker   │
                                            │  - “Has all ingredients” │
                                            └──────────┬───────────────┘
                                                       │
                                                       ▼
                                      ┌─────────────────────────────────┐
                                      │   LLM Adapter (guarded calls)  │
                                      │   - System prompt w/ constraints│
                                      │   - Few-shot examples           │
                                      │   - Tool-calls allowed          │
                                      └──────────┬──────────────────────┘
                                                 │
                               ┌─────────────────▼─────────────────┐
                               │  Post-Processor / Safety Net      │
                               │  - Re-validate diet/allergens     │
                               │  - Fix units/steps, enforce caps  │
                               │  - Fall back to non-LLM variant   │
                               └─────────────────┬─────────────────┘
                                                 │
                                                 ▼
                                 ┌───────────────────────────────────┐
                                 │  Response Builder                 │
                                 │  - Final recipe + steps           │
                                 │  - Substitutions list             │
                                 │  - Shopping list (missing items)  │
                                 └─────────────────┬─────────────────┘
                                                 │
                                                 ▼
                                      ┌────────────────────────┐
                                      │ Frontend (render)      │
                                      │ Ratings & feedback     │
                                      └──────────┬─────────────┘
                                                 │
                                                 ▼
                              ┌────────────────────────────────────┐
                              │  Analytics & Evaluation Pipeline  │
                              │  - A/B tests (prompt vs. hybrid)  │
                              │  - Success metrics (click, cook,  │
                              │    save, remake, time-to-answer)  │
                              │  - Offline eval (constraint pass %)│
                              └────────────────────────────────────┘

```

## 🛠️ Technical Components

1. **Frontend Layer**
   - React/Next.js based web interface
   - Responsive design for mobile/desktop
   - Real-time validation and feedback
   - User preference management
   - Recipe history and favorites

2. **API Gateway & Orchestration**
   - Authentication and rate limiting
   - Request validation and routing
   - Smart path selection (cache vs. LLM)
   - Comprehensive logging and monitoring

3. **Data Services**
   - **Cache Layer**
     - Redis for fast retrieval
     - Intelligent cache invalidation
     - Composite key strategy (ingredients + preferences)
   
   - **Retrieval Service**
     - Vector similarity search (FAISS/pgvector)
     - SQL database for structured recipe data
     - Efficient candidate selection
   
   - **Rules Engine**
     - Dietary restriction validation
     - Allergen filtering
     - Time and cost constraints

4. **Recipe Processing Pipeline**
   - **Validation Services**
     - Nutrition API integration
     - Unit standardization
     - Ingredient availability checks
   
   - **LLM Integration**
     - OpenAI API with guardrails
     - Context-aware prompting
     - Few-shot learning for substitutions
   
   - **Post-Processing**
     - Safety checks and validation
     - Unit/step standardization
     - Fallback mechanisms

5. **Analytics & Evaluation**
   - A/B testing framework
   - Success metrics tracking
   - Constraint validation
   - User feedback analysis

## 📋 Getting Started

[Coming Soon]
- Installation instructions
- Environment setup
- API configuration
- Running the application

## 🔧 Tech Stack

### Frontend
- **Framework**: React.js, Next.js
- **State Management**: Redux/MobX
- **UI Components**: Material-UI/Tailwind
- **API Client**: Axios/RTK Query

### Backend
- **API Gateway**: FastAPI/Express
- **Cache**: Redis
- **Databases**: 
  - PostgreSQL (with pgvector)
  - Vector Store (FAISS)
- **Search**: Elasticsearch

### ML/AI
- **LLM**: OpenAI API
- **Vector Embeddings**: sentence-transformers
- **Data Processing**: Pandas, NumPy
- **Validation**: pydantic

### DevOps
- **Container**: Docker
- **Orchestration**: Kubernetes
- **Monitoring**: Prometheus/Grafana
- **Logging**: ELK Stack

## 📝 License

[Coming Soon]

## 🤝 Contributing

[Coming Soon]

---
Built with ❤️ by akshat1198
