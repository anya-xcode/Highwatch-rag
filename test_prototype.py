import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_rag_system():
    print("🚀 Testing Highwatch RAG System...\n")
    
    # 1. Health Check
    try:
        health = requests.get(f"{BASE_URL}/health").json()
        print(f"✅ Health Check: {json.dumps(health, indent=2)}")
    except Exception as e:
        print(f"❌ Health Check failed: {e}")
        return

    # 2. List Documents (should be empty initially or have old ones)
    print("\nListing current documents...")
    docs = requests.get(f"{BASE_URL}/documents").json()
    print(f"Documents: {len(docs['documents'])}")

    # 3. Sync Drive (This might fail if tokens are invalid, but let's see)
    # print("\n🔄 Triggering Google Drive Sync...")
    # try:
    #     sync = requests.post(f"{BASE_URL}/sync-drive").json()
    #     print(f"Sync Result: {sync['message']}")
    # except Exception as e:
    #     print(f"❌ Sync failed (likely credentials/token issue): {e}")

    # 4. Upload a direct file for testing (since sync needs auth)
    print("\n📤 Uploading a sample document...")
    with open("sample_policy.txt", "w") as f:
        f.write("Highwatch AI Refund Policy: Customers can request a full refund within 30 days of purchase if they are unsatisfied with the service. To request a refund, contact support@highwatch.ai.")
    
    try:
        with open("sample_policy.txt", "rb") as f:
            files = {"file": ("sample_policy.txt", f, "text/plain")}
            upload = requests.post(f"{BASE_URL}/upload", files=files).json()
            print(f"Upload Result: {upload['message']}")
    except Exception as e:
        print(f"❌ Upload failed: {e}")

    # 5. Ask a question
    print("\n🤔 Asking a question...")
    query = {"query": "What is the refund policy and how many days do I have?"}
    try:
        answer = requests.post(f"{BASE_URL}/ask", json=query).json()
        print(f"\nAI ANSWER:\n{answer['answer']}")
        print(f"\nSOURCES: {answer['sources']}")
    except Exception as e:
        print(f"❌ Ask failed: {e}")

if __name__ == "__main__":
    test_rag_system()
