from typing import Optional, List, Dict, Any
import json
from groq import Groq
import os
from sqlalchemy.orm import Session
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

class AIAssistant:
    def __init__(self):
        self.groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.system_prompt = """You are an AI assistant for an e-commerce platform. Your role is to:
1. Help customers find products they're looking for
2. Provide product recommendations
3. Answer questions about orders
4. Assist with general inquiries

When responding:
1. Ask clarifying questions when needed
2. Use the provided database information to give accurate responses
3. Be concise but informative
4. If you don't have enough information, ask specific questions to gather it

The database has the following tables:
- products (id, name, category, brand, retail_price, department)
- orders (order_id, user_id, status, created_at, delivered_at)
- users (id, first_name, last_name, email)
"""

    def query_database(self, db: Session, query_type: str, **kwargs) -> List[Dict]:
        """Execute database queries based on the type of information needed"""
        if query_type == "products":
            # Query products based on filters
            query = text("""
                SELECT * FROM products 
                WHERE (:category IS NULL OR category = :category)
                AND (:department IS NULL OR department = :department)
                AND (:brand IS NULL OR brand = :brand)
                AND (:max_price IS NULL OR retail_price <= :max_price)
                LIMIT 5
            """)
            result = db.execute(query, kwargs)
            return [dict(row._mapping) for row in result]

        elif query_type == "order":
            # Query specific order details
            query = text("""
                SELECT o.*, oi.product_id, p.name as product_name, p.retail_price
                FROM orders o
                JOIN order_items oi ON o.order_id = oi.order_id
                JOIN products p ON oi.product_id = p.id
                WHERE o.order_id = :order_id
            """)
            result = db.execute(query, {"order_id": kwargs.get("order_id")})
            return [dict(row._mapping) for row in result]

        return []

    def generate_response(self, user_message: str, conversation_history: List[Dict], db: Session) -> str:
        # Format conversation history for the LLM
        formatted_history = []
        for msg in conversation_history:
            formatted_history.append({"role": msg["role"], "content": msg["content"]})

        # Prepare the messages for the LLM
        messages = [
            {"role": "system", "content": self.system_prompt},
            *formatted_history,
            {"role": "user", "content": user_message}
        ]

        try:
            # Get initial response from Groq
            completion = self.groq_client.chat.completions.create(
                model="mixtral-8x7b-32768",  # or another available model
                messages=messages,
                temperature=0.7,
                max_tokens=1000
            )
            
            ai_response = completion.choices[0].message.content

            # If the AI asks for specific information, query the database
            if any(keyword in ai_response.lower() for keyword in ["let me check", "let me search", "looking up"]):
                # Extract potential search parameters from the conversation
                search_params = self._extract_search_params(user_message, conversation_history)
                
                # Query the database
                products = self.query_database(db, "products", **search_params)
                
                # Include the database results in a follow-up message
                if products:
                    product_info = "\n".join([
                        f"- {p['name']} ({p['brand']}): ${p['retail_price']:.2f}" 
                        for p in products
                    ])
                    
                    messages.append({"role": "assistant", "content": ai_response})
                    messages.append({"role": "system", "content": f"Found these products:\n{product_info}"})
                    
                    # Get final response including the product information
                    completion = self.groq_client.chat.completions.create(
                        model="mixtral-8x7b-32768",
                        messages=messages,
                        temperature=0.7,
                        max_tokens=1000
                    )
                    return completion.choices[0].message.content
                
            return ai_response

        except Exception as e:
            return f"I apologize, but I encountered an error: {str(e)}. How else can I help you?"

    def _extract_search_params(self, user_message: str, conversation_history: List[Dict]) -> Dict[str, Any]:
        """Extract search parameters from the conversation"""
        # Combine current message with recent history
        full_context = " ".join([msg["content"] for msg in conversation_history] + [user_message])
        
        # Use Groq to extract structured parameters
        messages = [
            {"role": "system", "content": """Extract search parameters from the text. 
             Return only a JSON object with these possible keys: category, department, brand, max_price.
             If a parameter is not mentioned, don't include it."""},
            {"role": "user", "content": full_context}
        ]
        
        try:
            completion = self.groq_client.chat.completions.create(
                model="mixtral-8x7b-32768",
                messages=messages,
                temperature=0,
                max_tokens=100
            )
            
            # Parse the response as JSON
            response = completion.choices[0].message.content
            try:
                params = json.loads(response)
                return {k: v for k, v in params.items() if v is not None}
            except:
                return {}
                
        except:
            return {}
