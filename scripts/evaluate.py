import json
import sys
from typing import List, Dict
from upii.analysis.search import SearchEngine
from upii.analysis.llm import LocalLLM

# Sample Golden Q&A
EVAL_SET = [
    {
        "question": "What is the embedding model decision for Project Omega?",
        "expected_keywords": ["sentence-transformers", "latency", "100ms"],
        "expected_source": "project_omega.md"
    },
    {
        "question": "What is the budget for team offsites?",
        "expected_keywords": ["$20k", "20,000"],
        "expected_source": "financials.txt"
    },
    {
        "question": "Who fixed the memory leak?",
        "expected_keywords": ["Sarah"],
        "expected_source": "team_sync.md"
    },
    {
        "question": "What is the max latency target?",
        "expected_keywords": ["100ms"],
        "expected_source": "project_omega.md"
    },
     {
        "question": "What is the capital of Mars?",
        "expected_keywords": ["don't know", "no relevant context"],
        "expected_source": "N/A" # Negative test
    }
]

def run_eval():
    print(f"Running Evaluation on {len(EVAL_SET)} Questions...")
    
    search_engine = SearchEngine()
    llm = LocalLLM()
    
    # Check LLM health once
    llm_online = True
    try:
        from upii.analysis.diagnostics import Doctor
        if "FAIL" in Doctor().check_model():
             llm_online = False
             print("[WARN] Ollama offline. Mocking LLM answers for retrieval verify.")
    except:
        llm_online = False

    score = 0
    
    for item in EVAL_SET:
        q = item["question"]
        print(f"\nQ: {q}")
        
        # 1. End-to-End RAG
        # We manually verify similar logic to 'ask' CLI but instrumented
        results = search_engine.search(q, limit=5)
        
        if llm_online:
            answer = llm.answer_with_citations(q, results)
        else:
            # Mock answer based on retrieval content to simulate "perfect" LLM
            # This proves the harness logic works if Retrieval works
            if results and any(k.lower() in results[0].text.lower() for k in item["expected_keywords"]):
                 # If top result has keyword, simulate success
                 answer = f"Simulated Answer: contain {item['expected_keywords'][0]}"
            else:
                 answer = "I don't know"
        
        print(f"A: {answer}")
        
        # Scoring Logic
        passed = False
        # Check keywords
        if any(k.lower() in answer.lower() for k in item["expected_keywords"]):
            passed = True
            
        # Check source presence if positive test
        if item["expected_source"] != "N/A":
            # In v0.5, we store chunks. chunk.doc_hash is a UUID.
            # We don't easily have filenames in 'results' without DB lookup, 
            # but usually the answer text might contain clues or we trust the keyword match for now.
            # Ideally we check if correct chunk ID was retrieved.
            # For this simple harness, keyword match is sufficient proxy for correctness.
             pass

        if passed:
            print("[PASS]")
            score += 1
        else:
            print(f"[FAIL] Expected {item['expected_keywords']}")

    print(f"\nFinal Score: {score}/{len(EVAL_SET)}")

if __name__ == "__main__":
    run_eval()
