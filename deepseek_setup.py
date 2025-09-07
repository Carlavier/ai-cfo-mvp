# DeepSeek API Setup & Testing Script

import requests
import json
import os
from datetime import datetime

class DeepSeekAPITester:
    def __init__(self, api_key=None):
        # DeepSeek API credentials
        # Get your API key from: https://platform.deepseek.com/
        self.api_key = api_key or os.getenv('DEEPSEEK_API_KEY')
        self.base_url = "https://api.deepseek.com/v1/chat/completions"
        self.model = "deepseek-chat"
        
        if not self.api_key or self.api_key == "your_deepseek_key_here":
            print("⚠️  WARNING: No DeepSeek API key found!")
            print("💡 Get your free API key at: https://platform.deepseek.com/")
            print("💰 DeepSeek pricing: ~$0.14 per 1M input tokens (very cheap!)")
    
    def test_connection(self):
        """Test basic API connection"""
        print("🔍 Testing DeepSeek API connection...")
        
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "user", "content": "Hello! Please respond with 'API connection successful'"}
                ],
                "max_tokens": 50,
                "temperature": 0.1
            }
            
            response = requests.post(self.base_url, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                message = result['choices'][0]['message']['content']
                print(f"✅ DeepSeek API connection successful!")
                print(f"🤖 Response: {message}")
                return True
            else:
                print(f"❌ API Error: {response.status_code}")
                print(f"📝 Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    def test_financial_analysis(self):
        """Test financial analysis capabilities"""
        print("\n💰 Testing financial analysis capabilities...")
        
        # Sample financial data
        sample_data = {
            "current_cash": 47332.25,
            "monthly_burn": 28500,
            "outstanding_ar": 23400,
            "upcoming_ap": 15600,
            "runway_days": 127
        }
        
        prompt = f"""
        Analyze this financial situation and provide actionable recommendations:
        
        Financial Data:
        - Current cash: ${sample_data['current_cash']:,.2f}
        - Monthly burn rate: ${sample_data['monthly_burn']:,.2f}
        - Outstanding receivables: ${sample_data['outstanding_ar']:,.2f}
        - Upcoming payables: ${sample_data['upcoming_ap']:,.2f}
        - Cash runway: {sample_data['runway_days']} days
        
        Please provide:
        1. Assessment of financial health
        2. Top 3 actionable recommendations
        3. Risk factors to monitor
        """
        
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system", 
                        "content": "You are an expert AI CFO. Analyze financial data and provide specific, actionable insights with clear reasoning."
                    },
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 1000,
                "temperature": 0.3
            }
            
            start_time = datetime.now()
            response = requests.post(self.base_url, headers=headers, json=payload, timeout=30)
            end_time = datetime.now()
            
            response_time = (end_time - start_time).total_seconds()
            
            if response.status_code == 200:
                result = response.json()
                analysis = result['choices'][0]['message']['content']
                
                print(f"✅ Financial analysis completed!")
                print(f"⏱️  Response time: {response_time:.2f} seconds")
                print(f"📊 Analysis:")
                print("-" * 50)
                print(analysis)
                print("-" * 50)
                
                # Token usage info
                usage = result.get('usage', {})
                if usage:
                    print(f"📈 Token usage:")
                    print(f"   Input tokens: {usage.get('prompt_tokens', 0)}")
                    print(f"   Output tokens: {usage.get('completion_tokens', 0)}")
                    print(f"   Total tokens: {usage.get('total_tokens', 0)}")
                    
                    # Rough cost calculation (DeepSeek pricing)
                    cost = (usage.get('total_tokens', 0) / 1000000) * 0.14  # $0.14 per 1M tokens
                    print(f"   Estimated cost: ${cost:.4f}")
                
                return True
            else:
                print(f"❌ Analysis failed: {response.status_code}")
                print(f"📝 Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Analysis failed: {e}")
            return False
    
    def test_different_queries(self):
        """Test various CFO-related queries"""
        print("\n🧪 Testing various CFO queries...")
        
        test_queries = [
            "What's my cash runway and should I be worried?",
            "How can I improve my accounts receivable collection?", 
            "What are the biggest financial risks for my company?",
            "Should I pay bills early or preserve cash?",
            "How do I create a 13-week cash flow forecast?"
        ]
        
        for i, query in enumerate(test_queries, 1):
            print(f"\n🔍 Test {i}: {query}")
            
            try:
                headers = {
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json'
                }
                
                payload = {
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are an AI CFO assistant. Provide concise, actionable financial advice."
                        },
                        {"role": "user", "content": query}
                    ],
                    "max_tokens": 300,
                    "temperature": 0.2
                }
                
                response = requests.post(self.base_url, headers=headers, json=payload, timeout=20)
                
                if response.status_code == 200:
                    result = response.json()
                    answer = result['choices'][0]['message']['content']
                    print(f"✅ Response: {answer[:150]}...")
                else:
                    print(f"❌ Failed: {response.status_code}")
                    
            except Exception as e:
                print(f"❌ Error: {e}")

def setup_environment():
    """Setup environment for DeepSeek API"""
    print("🔧 DeepSeek API Setup Guide")
    print("=" * 50)
    
    print("\n1️⃣ Get your API key:")
    print("   • Go to: https://platform.deepseek.com/")
    print("   • Sign up for free account")
    print("   • Navigate to API Keys section")
    print("   • Create new API key")
    print("   • Copy the key (starts with 'sk-')")
    
    print("\n2️⃣ Set environment variable:")
    print("   Linux/Mac:")
    print("   export DEEPSEEK_API_KEY='your-api-key-here'")
    print("\n   Windows:")
    print("   set DEEPSEEK_API_KEY=your-api-key-here")
    
    print("\n3️⃣ Or add to .env file:")
    print("   DEEPSEEK_API_KEY=your-api-key-here")
    
    print("\n4️⃣ Pricing (very affordable):")
    print("   • Input: ~$0.14 per 1M tokens")
    print("   • Output: ~$0.28 per 1M tokens") 
    print("   • Typical query: <$0.001")
    print("   • 1000 queries ≈ $1")
    
    print("\n5️⃣ Benefits vs OpenAI:")
    print("   ✅ Much cheaper than GPT-4")
    print("   ✅ Good for financial analysis")
    print("   ✅ Fast response times")
    print("   ✅ No waitlists or approvals")

def main():
    print("🚀 DeepSeek API Setup & Testing")
    print("=" * 40)
    
    # Check if API key is available
    api_key = os.getenv('DEEPSEEK_API_KEY')
    
    if not api_key or api_key == "your_deepseek_key_here":
        setup_environment()
        
        print("\n" + "=" * 40)
        manual_key = input("Enter your DeepSeek API key to test (optional): ").strip()
        
        if manual_key and len(manual_key) > 10:
            api_key = manual_key
        else:
            print("❌ No API key provided. Exiting...")
            return
    
    # Initialize tester
    tester = DeepSeekAPITester(api_key)
    
    # Run tests
    print("\n🧪 Running API Tests...")
    print("=" * 30)
    
    # Basic connection test
    if not tester.test_connection():
        print("❌ Basic connection failed. Check your API key.")
        return
    
    # Financial analysis test
    if not tester.test_financial_analysis():
        print("❌ Financial analysis test failed.")
        return
    
    # Multiple queries test
    tester.test_different_queries()
    
    print("\n🎉 All tests completed!")
    print("✅ DeepSeek API is ready for your AI CFO app!")
    
    # Integration guidance
    print("\n📝 Next steps:")
    print("1. Add DEEPSEEK_API_KEY to your environment")
    print("2. Run your Streamlit app: streamlit run ai_cfo_mvp.py")
    print("3. Test the AI Chat feature")
    print("4. Deploy to Streamlit Cloud with secrets")

if __name__ == "__main__":
    main()

# Alternative: Simple test without class
def quick_test():
    """Quick test function"""
    api_key = input("Enter your DeepSeek API key: ").strip()
    
    if not api_key:
        print("No API key provided")
        return
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "user", "content": "Analyze: I have $50K cash, $5K monthly burn. What's my runway?"}
        ],
        "max_tokens": 200
    }
    
    try:
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers, 
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Success!")
            print(f"Response: {result['choices'][0]['message']['content']}")
        else:
            print(f"❌ Error {response.status_code}: {response.text}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

# Uncomment to run quick test:
# quick_test()