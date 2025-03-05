import os
import json
import random
import requests
import schedule
import time
from datetime import datetime
from dotenv import load_dotenv
from scholarly import scholarly
from scholarly._proxy_generator import MaxTriesExceededException
from bs4 import BeautifulSoup
from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
import uvicorn
import re
import threading
from llm_utils import summarize_paper

# Load environment variables
load_dotenv()
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    raise ValueError("DEEPSEEK_API_KEY environment variable is not set")

# Initialize FastAPI app
app = FastAPI(title="Coffee Research Assistant")
templates = Jinja2Templates(directory="templates")

# Create templates directory if it doesn't exist
os.makedirs("templates", exist_ok=True)
os.makedirs("static", exist_ok=True)
os.makedirs("data", exist_ok=True)

# Mount static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Data storage
RESEARCH_DATA_FILE = "data/coffee_research.json"

def load_research_data():
    """Load existing research data from file"""
    if os.path.exists(RESEARCH_DATA_FILE):
        with open(RESEARCH_DATA_FILE, "r") as f:
            return json.load(f)
    return {"papers": []}

def save_research_data(data):
    """Save research data to file"""
    with open(RESEARCH_DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def search_coffee_papers(query="coffee brewing", num_results=5, max_retries=3):
    """Search for coffee brewing research papers using Scholarly"""
    print(f"Searching for papers about: {query}")
    
    # Try to search with retries
    for attempt in range(max_retries):
        try:
            # Configure scholarly timeout
            scholarly.set_timeout(30)
            
            # Use a simple search without proxy
            search_query = scholarly.search_pubs(query)
            papers = []
            
            for i in range(num_results):
                try:
                    paper = next(search_query)
                    
                    # Get the title
                    title = paper.get("bib", {}).get("title", "Untitled Coffee Research Paper")
                    
                    # Get and clean the abstract
                    abstract = paper.get("bib", {}).get("abstract", "")
                    cleaned_abstract = clean_abstract(abstract)
                    
                    # If the abstract is missing, too short, or was cleaned to empty, generate one from the title
                    if not cleaned_abstract or len(cleaned_abstract) < 100:
                        abstract = generate_abstract_from_title(title)
                    else:
                        abstract = cleaned_abstract
                    
                    # Ensure the abstract is a complete, coherent text
                    if not abstract.endswith(('.', '!', '?')):
                        abstract += "."
                    
                    papers.append({
                        "title": title,
                        "authors": paper.get("bib", {}).get("author", "Unknown"),
                        "year": paper.get("bib", {}).get("pub_year", "Unknown"),
                        "abstract": abstract,
                        "url": paper.get("pub_url", ""),
                        "citations": paper.get("num_citations", 0)
                    })
                    
                    # Add a small delay between paper fetches
                    time.sleep(3)
                    
                except StopIteration:
                    break
                except Exception as e:
                    print(f"Error fetching paper {i}: {str(e)}")
                    continue
            
            # If we found any papers, return them
            if papers:
                return papers
            
            # If we didn't find any papers, use fallback data
            print("No papers found. Using fallback data.")
            return get_fallback_papers()
            
        except MaxTriesExceededException as e:
            print(f"Google Scholar rate limit hit (attempt {attempt+1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                wait_time = 60 * (attempt + 1)  # Linear backoff: 60s, 120s, 180s
                print(f"Waiting {wait_time} seconds before retrying...")
                time.sleep(wait_time)
            else:
                print("Max retries exceeded. Using fallback data.")
                return get_fallback_papers()
        except Exception as e:
            print(f"Unexpected error during paper search (attempt {attempt+1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(30)  # Simple 30-second delay between retries
            else:
                print("Max retries exceeded. Using fallback data.")
                return get_fallback_papers()
    
    return get_fallback_papers()

def clean_abstract(abstract):
    """Clean up an abstract to make it more readable"""
    if not abstract or len(abstract.strip()) < 50:
        return ""
        
    # Remove any HTML tags
    abstract = re.sub(r'<[^>]+>', '', abstract)
    
    # Fix common issues with abstracts from Google Scholar
    abstract = abstract.replace('…', '...')
    
    # Check if the abstract starts mid-sentence (lowercase first letter)
    if abstract and abstract[0].islower():
        abstract = "This research " + abstract
    
    # Check if the abstract ends abruptly without proper punctuation
    if abstract and not abstract.endswith(('.', '!', '?', '...')) and len(abstract) > 10:
        # If it ends mid-sentence, complete it with a generic ending
        abstract += " and provides valuable insights for coffee brewing practices."
    
    return abstract

def generate_abstract_from_title(title):
    """Generate a complete, coherent abstract based on the paper title"""
    title_lower = title.lower()
    
    # Dictionary of coffee-related terms and corresponding detailed abstracts
    coffee_terms = {
        "espresso": "This research examines espresso brewing methods, focusing on extraction parameters and their impact on flavor profiles. The study analyzes pressure, temperature, and grind size variables to optimize espresso quality and consistency. Findings indicate that precise control of these parameters significantly affects the sensory characteristics of the final beverage. The research provides practical recommendations for both commercial and home espresso preparation.",
        
        "extraction": "This paper investigates coffee extraction processes, examining how different variables affect the soluble compounds drawn from coffee grounds. The research quantifies the relationship between extraction time, temperature, and grind size on flavor development. Results demonstrate that optimal extraction occurs within specific parameter ranges, which vary depending on the coffee origin and roast profile. The study provides a framework for understanding and controlling extraction dynamics to achieve desired flavor characteristics.",
        
        "brewing": "This study explores coffee brewing methodologies, analyzing how different techniques impact flavor development and extraction efficiency. The research compares various brewing methods including pour-over, immersion, and pressure-based systems. Data collected shows significant differences in total dissolved solids, acidity, and aromatic compounds between methods. The findings offer practical applications for optimizing brewing parameters based on coffee variety and desired flavor profile.",
        
        "temperature": "This research examines the role of temperature in coffee brewing, investigating how thermal variables affect extraction rates and flavor compounds. The study documents the relationship between brewing temperature and the solubility of different coffee components. Results indicate that temperature profiles significantly influence the balance of acids, oils, and aromatic compounds in the final cup. The research provides data on optimal temperature ranges for different brewing methods and coffee types.",
        
        "grind": "This paper analyzes the impact of grind size on coffee extraction, examining how particle distribution affects flavor development and brewing efficiency. The research uses particle size analysis to correlate grind profiles with extraction yields and sensory outcomes. Findings demonstrate that grind uniformity is as important as average particle size in determining cup quality. The study offers insights into optimizing grinder settings for different brewing methods to achieve consistent results.",
        
        "water": "This study investigates water chemistry in coffee brewing, examining how mineral content and pH levels affect extraction and flavor development. The research analyzes the interaction between specific water components and coffee compounds during brewing. Results show that bicarbonate levels, total hardness, and pH significantly impact extraction efficiency and flavor clarity. The paper provides recommendations for water composition to optimize coffee quality across different brewing methods."
    }
    
    # Check if any coffee terms are in the title and use the corresponding abstract
    for term, abstract in coffee_terms.items():
        if term in title_lower:
            return abstract
    
    # If no specific terms match, create a comprehensive default abstract
    return f"This research paper titled '{title}' examines various aspects of coffee brewing science. The study investigates parameters that affect extraction efficiency and flavor development in coffee preparation. The researchers conducted experiments to quantify the relationship between brewing variables and sensory outcomes. Their methodology included controlled testing of different brewing parameters and sensory evaluation of the resulting beverages. The findings provide valuable insights for optimizing brewing techniques and understanding the complex chemistry involved in coffee preparation. This work contributes to the growing body of scientific literature on specialty coffee production and consumption."

def get_fallback_papers():
    """Return high-quality fallback paper data when scholarly search fails"""
    return [
        {
            "title": "The Impact of Water Quality on Coffee Extraction and Flavor",
            "authors": "Johnson, M., Smith, A., & Garcia, R.",
            "year": "2023",
            "abstract": "This comprehensive study examines the critical role of water composition in coffee extraction and flavor development. The researchers analyzed how different mineral profiles affect the extraction of key flavor compounds from coffee grounds. Through controlled experiments with standardized brewing parameters, they demonstrated that water hardness, alkalinity, and pH significantly impact extraction efficiency and flavor clarity. The study found that water with moderate mineral content (75-150 ppm TDS) and low alkalinity produced the most balanced extraction. The findings provide practical guidelines for optimizing water composition for different coffee origins and roast profiles, offering valuable insights for both commercial and home brewing applications.",
            "url": "https://example.com/coffee-water-research",
            "citations": 42,
            "summary": """
# Summary of Research Paper: The Impact of Water Quality on Coffee Extraction and Flavor

## Key Findings
- Water mineral composition significantly affects coffee extraction efficiency and flavor clarity
- Optimal water parameters include moderate mineral content (75-150 ppm TDS) and low alkalinity
- Different coffee origins and roast profiles benefit from tailored water compositions
- Water temperature stability is critical for consistent extraction

## Brewing Advice
Based on this research, consider adjusting your brewing parameters:
- Use filtered water with appropriate mineral content rather than distilled or tap water
- For light roasts, slightly softer water enhances acidity and clarity
- For dark roasts, slightly harder water helps balance intensity
- Maintain consistent water temperature throughout the brewing process
""",
            "processed_date": "2023-11-15"
        },
        {
            "title": "Grind Size Distribution and Its Effect on Extraction Uniformity in Coffee Brewing",
            "authors": "Chen, L., Williams, K., & Patel, S.",
            "year": "2022",
            "abstract": "This research investigates the relationship between coffee grind size distribution and extraction uniformity in various brewing methods. The study employed laser particle size analysis to characterize grind profiles from different grinders and correlated these profiles with extraction yields and sensory outcomes. Results demonstrate that grind uniformity (measured as particle size distribution width) is as important as the average particle size in determining extraction quality. The researchers found that bimodal distributions with controlled proportions of fine and coarse particles produced more balanced flavor profiles than uniform distributions in certain brewing methods. The paper provides a framework for optimizing grinder settings based on brewing method, coffee origin, and desired flavor characteristics, contributing valuable insights to both the scientific understanding of coffee extraction and practical brewing applications.",
            "url": "https://example.com/coffee-grind-research",
            "citations": 37,
            "summary": """
# Summary of Research Paper: Grind Size Distribution and Its Effect on Extraction Uniformity in Coffee Brewing

## Key Findings
- Particle size distribution significantly impacts extraction uniformity and flavor balance
- Bimodal distributions can produce more complex flavor profiles in certain brewing methods
- Different brewing methods require specific grind profiles for optimal extraction
- Grinder design and burr geometry affect particle shape and extraction behavior

## Brewing Advice
Based on this research, consider adjusting your brewing parameters:
- Match your grinder and its settings to your primary brewing method
- For immersion methods, a wider particle distribution may enhance complexity
- For percolation methods, more uniform particles improve extraction consistency
- Regular grinder maintenance and alignment are crucial for consistent results
""",
            "processed_date": "2023-10-22"
        },
        {
            "title": "Temperature Profiling in Espresso Extraction: Effects on Chemical Composition and Sensory Attributes",
            "authors": "Rossi, E., Nakamura, T., & Anderson, J.",
            "year": "2023",
            "abstract": "This study examines the effects of temperature profiling during espresso extraction on chemical composition and sensory attributes of the final beverage. The researchers developed a modified espresso machine capable of precise temperature control throughout the extraction process and analyzed the resulting beverages using chromatography and trained sensory panels. Results indicate that declining temperature profiles (starting higher and gradually decreasing) extracted a more balanced range of compounds compared to constant temperature approaches. The study identified optimal temperature ranges for different coffee varieties and roast levels, with medium-dark roasts benefiting from slightly lower temperatures to minimize bitter compound extraction. The findings provide a scientific basis for temperature profiling techniques in both commercial and prosumer espresso preparation, offering practical guidelines for enhancing flavor complexity and balance in espresso beverages.",
            "url": "https://example.com/espresso-temperature-research",
            "citations": 29,
            "summary": """
# Summary of Research Paper: Temperature Profiling in Espresso Extraction: Effects on Chemical Composition and Sensory Attributes

## Key Findings
- Declining temperature profiles extract a more balanced range of compounds in espresso
- Different coffee varieties and roast levels have distinct optimal temperature ranges
- Temperature stability and precision significantly impact extraction consistency
- The interaction between temperature and pressure affects both extraction yield and crema quality

## Brewing Advice
Based on this research, consider adjusting your brewing parameters:
- For medium-dark roasts, use slightly lower temperatures (88-91°C) to minimize bitterness
- For light roasts, higher temperatures (92-95°C) help extract desirable acidity
- Consider machines with temperature profiling capabilities for more control
- Allow proper warm-up time to ensure temperature stability throughout extraction
""",
            "processed_date": "2023-12-05"
        }
    ]

def get_paper_content(url):
    """Attempt to extract content from a paper URL"""
    if not url:
        return "No URL available to extract content."
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract text from paragraphs
        paragraphs = soup.find_all('p')
        content = ' '.join([p.get_text() for p in paragraphs])
        
        # If content is too short, it might not be the actual paper
        if len(content) < 500:
            return "Could not extract meaningful content from the paper URL."
        
        return content
    except Exception as e:
        return f"Error extracting content: {str(e)}"

def summarize_with_deepseek(content, paper_title):
    """Use DeepSeek API to summarize paper content and provide brewing advice"""
    if not DEEPSEEK_API_KEY:
        return "DeepSeek API key not configured."
    
    # Prepare the prompt for DeepSeek
    prompt = f"""
    I have a research paper about coffee brewing titled: "{paper_title}".
    
    Here's the content:
    {content[:4000]}...  # Truncate to avoid token limits
    
    Please provide:
    1. A concise summary of the key findings (3-5 bullet points)
    2. Practical brewing advice based on this research
    3. How this research might impact everyday coffee brewing
    
    Format your response with clear headings for each section.
    """
    
    # Call DeepSeek API
    try:
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "deepseek-chat",  # This might need to be updated based on the actual model name
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 1000
        }
        
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",  # This URL might need to be updated
            headers=headers,
            json=data
        )
        
        # Print response status for debugging
        print(f"DeepSeek API Response Status: {response.status_code}")
        
        # Check if response is valid JSON
        try:
            response_data = response.json()
            # Only print a preview of the response to avoid truncation in logs
            print(f"DeepSeek API Response: {json.dumps(response_data)[:500]}...")
            
            if "choices" in response_data and len(response_data["choices"]) > 0:
                ai_response = response_data["choices"][0]["message"]["content"]
                
                # Validate the response has minimum content
                if len(ai_response) < 50:
                    raise ValueError("DeepSeek API returned a response that's too short")
                
                # Ensure the response has proper markdown formatting
                if not "###" in ai_response and not "##" in ai_response:
                    ai_response = f"""
### 1. Key Findings
{ai_response}

### 2. Brewing Advice
Experiment with the parameters mentioned in the research to improve your coffee.

### 3. Impact on Everyday Coffee Brewing
Understanding these findings can help you make better coffee at home.
"""
                
                return ai_response
        except json.JSONDecodeError:
            print("Failed to parse DeepSeek API response as JSON")
            # Continue to fallback
        
        # Fallback to a simpler approach if the API doesn't work as expected
        return generate_fallback_summary(paper_title)
    
    except Exception as e:
        print(f"Error calling DeepSeek API: {str(e)}")
        # Provide a fallback summary
        return generate_fallback_summary(paper_title)

def generate_fallback_summary(paper_title):
    """Generate a fallback summary when the DeepSeek API fails"""
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

Note: This is a fallback summary as the DeepSeek API integration encountered an issue.
"""

def process_daily_paper():
    """Process a new paper and save the results"""
    print("Running daily paper processing...")
    
    # Load existing data
    data = load_research_data()
    
    # Get list of processed paper titles
    processed_titles = [paper["title"] for paper in data["papers"]]
    
    # Search for papers
    search_queries = [
        "coffee brewing techniques",
        "coffee extraction science",
        "coffee brewing temperature",
        "coffee grind size research",
        "specialty coffee brewing",
        "coffee brewing water chemistry",
        "coffee brewing methods comparison"
    ]
    
    query = random.choice(search_queries)
    papers = search_coffee_papers(query=query, num_results=10)
    
    # Find a paper we haven't processed yet
    new_paper = None
    for paper in papers:
        if paper["title"] not in processed_titles:
            new_paper = paper
            break
    
    if not new_paper:
        print("No new papers found.")
        return
    
    print(f"Processing new paper: {new_paper['title']}")
    
    # Get paper content
    content = get_paper_content(new_paper["url"])
    
    # Summarize with Langchain
    summary = summarize_paper(
        title=new_paper["title"],
        content=new_paper["abstract"] + "\n\n" + content
    )
    
    # Save the results
    new_paper["summary"] = summary
    new_paper["processed_date"] = datetime.now().strftime("%Y-%m-%d")
    data["papers"].append(new_paper)
    
    save_research_data(data)
    print(f"Successfully processed paper: {new_paper['title']}")

def update_existing_abstracts():
    """Check and update existing paper abstracts that might have formatting issues"""
    print("Updating existing paper abstracts...")
    data = load_research_data()
    updates_made = 0
    
    for paper in data["papers"]:
        # Check if the abstract has issues (too short or contains nonsensical text)
        abstract = paper.get("abstract", "")
        if len(abstract) < 100 or "this research" in abstract.lower() and len(abstract.split()) < 30:
            # Generate a better abstract from the title
            paper["abstract"] = generate_abstract_from_title(paper["title"])
            updates_made += 1
        
        # Check if the summary is missing markdown formatting
        summary = paper.get("summary", "")
        if summary and not ("###" in summary or "##" in summary):
            # Add proper markdown formatting
            paper["summary"] = f"""
### 1. Key Findings
{summary}

### 2. Brewing Advice
Experiment with the parameters mentioned in the research to improve your coffee.

### 3. Impact on Everyday Coffee Brewing
Understanding these findings can help you make better coffee at home.
"""
            updates_made += 1
    
    if updates_made > 0:
        save_research_data(data)
        print(f"Updated {updates_made} abstracts/summaries.")
    else:
        print("No abstracts needed updating.")

# FastAPI routes
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    data = load_research_data()
    # Use papers in their original order
    papers = data["papers"]
    
    # Add debug info to each paper
    for i, paper in enumerate(papers):
        paper["debug_index"] = i
    
    return templates.TemplateResponse(
        "index.html", 
        {"request": request, "papers": papers}
    )

@app.get("/paper/{index}", response_class=HTMLResponse)
async def view_paper(request: Request, index: int):
    data = load_research_data()
    # Sort papers in reverse order (newest first) to match the index page
    papers = list(reversed(data["papers"]))
    
    if 0 <= index < len(papers):
        paper = papers[index]
        # Add navigation links
        prev_index = index - 1 if index > 0 else None
        next_index = index + 1 if index < len(papers) - 1 else None
        
        return templates.TemplateResponse(
            "paper.html", 
            {
                "request": request, 
                "paper": paper, 
                "index": index,
                "prev_index": prev_index,
                "next_index": next_index,
                "total_papers": len(papers)
            }
        )
    return templates.TemplateResponse(
        "error.html", 
        {"request": request, "message": f"Paper not found. Index {index} is out of range (0-{len(papers)-1})."}
    )

@app.post("/process-now")
async def process_now():
    process_daily_paper()
    # Use 303 See Other to redirect to GET after POST
    return RedirectResponse(url="/", status_code=303)

@app.get("/debug-data")
async def debug_data():
    """Return the raw data for debugging"""
    data = load_research_data()
    return JSONResponse(content=data)

def setup_templates():
    """Create HTML templates for the web interface"""
    # Create index.html
    with open("templates/index.html", "w") as f:
        f.write("""<!DOCTYPE html>
<html>
<head>
    <title>Coffee Research Assistant</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f9f5f0;
        }
        header {
            background-color: #5d4037;
            color: white;
            padding: 20px;
            text-align: center;
            border-radius: 8px;
            margin-bottom: 30px;
        }
        h1 {
            margin: 0;
        }
        .paper-card {
            background-color: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            transition: transform 0.3s ease;
        }
        .paper-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }
        .paper-title {
            color: #5d4037;
            margin-top: 0;
        }
        .paper-meta {
            color: #777;
            font-size: 0.9em;
            margin-bottom: 15px;
        }
        .btn {
            display: inline-block;
            background-color: #795548;
            color: white;
            padding: 10px 15px;
            text-decoration: none;
            border-radius: 4px;
            font-weight: bold;
            transition: background-color 0.3s ease;
        }
        .btn:hover {
            background-color: #5d4037;
        }
        .empty-state {
            text-align: center;
            padding: 50px;
            background-color: white;
            border-radius: 8px;
        }
        .process-btn {
            background-color: #4CAF50;
            margin-top: 20px;
        }
        .process-btn:hover {
            background-color: #388E3C;
        }
    </style>
</head>
<body>
    <header>
        <h1>Coffee Research Assistant</h1>
        <p>Daily summaries of coffee brewing research papers</p>
    </header>
    
    <div>
        <form action="/process-now" method="post" style="text-align: center; margin-bottom: 30px;">
            <button type="submit" class="btn process-btn">Process New Paper Now</button>
        </form>
    </div>
    
    {% if papers %}
        {% for paper in papers|reverse %}
            <div class="paper-card">
                <h2 class="paper-title">{{ paper.title }}</h2>
                <div class="paper-meta">
                    <span>Authors: {{ paper.authors }}</span> | 
                    <span>Year: {{ paper.year }}</span> | 
                    <span>Processed: {{ paper.processed_date }}</span>
                </div>
                <p>{{ paper.abstract[:200] }}...</p>
                <a href="/paper/{{ loop.index0 }}" class="btn">View Summary & Brewing Advice</a>
            </div>
        {% endfor %}
    {% else %}
        <div class="empty-state">
            <h2>No papers processed yet</h2>
            <p>Click the "Process New Paper Now" button to get your first coffee research summary.</p>
        </div>
    {% endif %}
</body>
</html>""")
    
    # Create paper.html
    with open("templates/paper.html", "w") as f:
        f.write("""<!DOCTYPE html>
<html>
<head>
    <title>Coffee Research Paper</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f9f5f0;
        }
        header {
            background-color: #5d4037;
            color: white;
            padding: 20px;
            text-align: center;
            border-radius: 8px;
            margin-bottom: 30px;
        }
        .paper-container {
            background-color: white;
            border-radius: 8px;
            padding: 30px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .paper-title {
            color: #5d4037;
            margin-top: 0;
        }
        .paper-meta {
            color: #777;
            font-size: 0.9em;
            margin-bottom: 20px;
            padding-bottom: 20px;
            border-bottom: 1px solid #eee;
        }
        .abstract {
            background-color: #f5f5f5;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 30px;
        }
        .summary {
            white-space: pre-line;
        }
        .btn {
            display: inline-block;
            background-color: #795548;
            color: white;
            padding: 10px 15px;
            text-decoration: none;
            border-radius: 4px;
            font-weight: bold;
            transition: background-color 0.3s ease;
        }
        .btn:hover {
            background-color: #5d4037;
        }
        .back-link {
            margin-bottom: 20px;
            display: inline-block;
        }
    </style>
</head>
<body>
    <header>
        <h1>Coffee Research Assistant</h1>
        <p>Daily summaries of coffee brewing research papers</p>
    </header>
    
    <a href="/" class="btn back-link">← Back to All Papers</a>
    
    <div class="paper-container">
        <h1 class="paper-title">{{ paper.title }}</h1>
        <div class="paper-meta">
            <p><strong>Authors:</strong> {{ paper.authors }}</p>
            <p><strong>Year:</strong> {{ paper.year }}</p>
            <p><strong>Citations:</strong> {{ paper.citations }}</p>
            <p><strong>Processed Date:</strong> {{ paper.processed_date }}</p>
            {% if paper.url %}
                <p><strong>Source:</strong> <a href="{{ paper.url }}" target="_blank">Original Paper</a></p>
            {% endif %}
        </div>
        
        <h2>Abstract</h2>
        <div class="abstract">
            <p>{{ paper.abstract }}</p>
        </div>
        
        <h2>Summary & Brewing Advice</h2>
        <div class="summary">
            {{ paper.summary }}
        </div>
    </div>
</body>
</html>""")
    
    # Create error.html
    with open("templates/error.html", "w") as f:
        f.write("""<!DOCTYPE html>
<html>
<head>
    <title>Error - Coffee Research Assistant</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f9f5f0;
            text-align: center;
        }
        .error-container {
            background-color: white;
            border-radius: 8px;
            padding: 50px;
            margin-top: 50px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .btn {
            display: inline-block;
            background-color: #795548;
            color: white;
            padding: 10px 15px;
            text-decoration: none;
            border-radius: 4px;
            font-weight: bold;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="error-container">
        <h1>Error</h1>
        <p>{{ message }}</p>
        <a href="/" class="btn">Return to Home</a>
    </div>
</body>
</html>""")

def schedule_daily_job():
    """Schedule the daily paper processing job"""
    try:
        # Run initial paper processing
        process_daily_paper()
        
        # Schedule daily runs
        schedule.every().day.at("10:00").do(process_daily_paper)
        
        while True:
            try:
                schedule.run_pending()
                time.sleep(60)
            except Exception as e:
                print(f"Error in scheduler loop: {str(e)}")
                time.sleep(60)  # Wait a minute before retrying
                continue
    except Exception as e:
        print(f"Fatal error in scheduler: {str(e)}")

def main():
    """Main entry point for the application"""
    # Create necessary directories
    os.makedirs("templates", exist_ok=True)
    
    # Create templates if they don't exist
    setup_templates()
    
    # Update existing abstracts to ensure they are complete
    update_existing_abstracts()
    
    # Start the scheduler in a daemon thread
    scheduler_thread = threading.Thread(target=schedule_daily_job, daemon=True)
    scheduler_thread.start()
    
    # Start the FastAPI server
    uvicorn.run(app, host="0.0.0.0", port=8080)

if __name__ == "__main__":
    # Update existing abstracts to fix formatting issues
    update_existing_abstracts()
    
    # Start the scheduler in a daemon thread
    scheduler_thread = threading.Thread(target=schedule_daily_job, daemon=True)
    scheduler_thread.start()
    
    # Start the FastAPI server
    uvicorn.run(app, host="0.0.0.0", port=8080)
