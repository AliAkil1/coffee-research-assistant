from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.llms.base import LLM
from typing import Optional, Any, List, Mapping
import os
from dotenv import load_dotenv
import requests
import json

# Load environment variables
load_dotenv()
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

class DeepSeekLLM(LLM):
    """Custom LLM class for DeepSeek API"""
    
    model_name: str = "deepseek-chat"
    temperature: float = 0.7
    max_tokens: int = 1000
    api_key: str = DEEPSEEK_API_KEY
    
    @property
    def _llm_type(self) -> str:
        return "deepseek"
    
    def _call(self, prompt: str, stop: Optional[List[str]] = None, **kwargs: Any) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }
        
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers,
            json=data
        )
        
        if response.status_code != 200:
            raise ValueError(f"API call failed: {response.text}")
            
        response_data = response.json()
        return response_data["choices"][0]["message"]["content"]

# Initialize the DeepSeek LLM
llm = DeepSeekLLM()

# Define prompt templates
PAPER_SUMMARY_TEMPLATE = """
I have a research paper about coffee brewing titled: "{title}".

Here's the content:
{content}

Please provide:
1. A concise summary of the key findings (3-5 bullet points)
2. Practical brewing advice based on this research
3. How this research might impact everyday coffee brewing

Format your response with clear headings for each section.
"""

paper_summary_prompt = PromptTemplate(
    input_variables=["title", "content"],
    template=PAPER_SUMMARY_TEMPLATE
)

# Create chains
paper_summary_chain = LLMChain(
    llm=llm,
    prompt=paper_summary_prompt,
    verbose=True
)

def summarize_paper(title: str, content: str) -> Optional[str]:
    """
    Summarize a paper using Langchain and DeepSeek.
    
    Args:
        title: The title of the paper
        content: The content to summarize (abstract + full text)
        
    Returns:
        str: A formatted summary of the paper, or None if there's an error
    """
    try:
        # Truncate content to avoid token limits
        truncated_content = content[:4000] + "..." if len(content) > 4000 else content
        
        # Run the chain
        result = paper_summary_chain.run(
            title=title,
            content=truncated_content
        )
        
        # Validate the response
        if len(result) < 50:
            raise ValueError("Generated summary is too short")
            
        # Ensure proper markdown formatting
        if not "###" in result and not "##" in result:
            result = f"""
### 1. Key Findings
{result}

### 2. Brewing Advice
Experiment with the parameters mentioned in the research to improve your coffee.

### 3. Impact on Everyday Coffee Brewing
Understanding these findings can help you make better coffee at home.
"""
        
        return result
        
    except Exception as e:
        print(f"Error in Langchain paper summarization: {str(e)}")
        return generate_fallback_summary(title)

def generate_fallback_summary(title: str) -> str:
    """Generate a fallback summary when the LLM fails"""
    return f"""
### 1. Key Findings
- The research explores various aspects of coffee brewing techniques and parameters
- It highlights the importance of water temperature, grind size, and brewing time
- The study provides evidence-based recommendations for optimal extraction

### 2. Brewing Advice
Based on this research, consider adjusting your brewing parameters:
- Use water between 90-96°C for optimal extraction
- Adjust grind size according to your brewing method
- Pay attention to the coffee-to-water ratio for consistency

### 3. Impact on Everyday Coffee Brewing
This research suggests that small adjustments to your brewing routine can significantly enhance flavor. Experimenting with the variables mentioned above can help you discover your preferred coffee profile.

Note: This is a fallback summary as the LLM integration encountered an issue.
""" 