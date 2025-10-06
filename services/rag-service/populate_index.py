#!/usr/bin/env python3

from pinecone import Pinecone
import os
from sentence_transformers import SentenceTransformer

def populate_pinecone_index():
    """Populate Pinecone index with sample CrashPay banking documents."""
    
    # Initialize Pinecone
    api_key = os.getenv('PINECONE_API_KEY')
    if not api_key:
        print("❌ PINECONE_API_KEY not found")
        return
        
    print("🌲 Initializing Pinecone 3.x...")
    pc = Pinecone(api_key=api_key)
    index = pc.Index('fake-fintech-rag')

    # Initialize embeddings
    print("🤖 Loading embedding model...")
    model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')

    # Sample CrashPay banking documents
    docs = [
        {
            'id': 'routing-1', 
            'text': 'CrashPay Bank routing number is 123456789. Use this for wire transfers and ACH transactions. Our SWIFT code is CRASHPAYUS33.'
        },
        {
            'id': 'support-1', 
            'text': 'CrashPay customer support phone number is 1-800-CRASH-PAY (1-800-272-7472). Available 24/7 for account assistance.'
        },
        {
            'id': 'hours-1', 
            'text': 'CrashPay bank hours: Monday-Friday 9AM-5PM EST. Online banking available 24/7. Weekend customer service 10AM-2PM.'
        },
        {
            'id': 'account-1',
            'text': 'CrashPay offers checking accounts, savings accounts, and credit cards. Minimum opening deposit is $25 for checking accounts.'
        },
        {
            'id': 'fees-1',
            'text': 'CrashPay monthly maintenance fee is $12 for checking accounts. Fee waived with direct deposit or minimum balance of $1500.'
        }
    ]

    # Upload documents
    print("📝 Uploading documents to Pinecone...")
    for doc in docs:
        embedding = model.encode(doc['text']).tolist()
        index.upsert([(doc['id'], embedding, {'text': doc['text']})])
        print(f'   ✅ Uploaded: {doc["id"]}')

    print('🎉 All documents uploaded to Pinecone successfully!')
    
    # Test query
    print("\n🔍 Testing a sample query...")
    query_text = "What is the routing number?"
    query_embedding = model.encode(query_text).tolist()
    results = index.query(vector=query_embedding, top_k=3, include_metadata=True)
    
    print(f"Query: '{query_text}'")
    for match in results['matches']:
        print(f"  Score: {match['score']:.3f} - {match['metadata']['text'][:100]}...")

if __name__ == "__main__":
    populate_pinecone_index() 