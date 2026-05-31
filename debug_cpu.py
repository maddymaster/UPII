import ollama
import time

print("Attempting CPU-only inference...")
try:
    # Force CPU to avoid Metal/GPU issues
    response = ollama.generate(
        model="llama3.2", 
        prompt="Why is the sky blue?", 
        options={"num_gpu": 0}
    )
    print("Success!")
    print(response['response'])
except Exception as e:
    print(f"Failed: {e}")
