# Coffee Research Assistant

A web application that automatically discovers, analyzes, and summarizes academic research papers about coffee brewing. It provides practical brewing advice derived from scientific research, making academic knowledge accessible to coffee enthusiasts.

![Coffee Research Assistant Screenshot](docs/screenshot.png)

## Features

- 🔍 Automated daily search and processing of coffee brewing research papers
- 🤖 AI-powered summarization using DeepSeek AI
- ☕ Extraction of practical brewing advice from academic research
- 🌐 Clean, responsive web interface
- 📊 Detailed paper analysis including citations and impact
- 📱 Mobile-friendly design
- 🔄 Manual trigger to process new papers on demand

## Requirements

- Python 3.8+
- DeepSeek API key (Get one at [DeepSeek AI](https://deepseek.ai))
- 500MB+ free disk space
- Internet connection for paper fetching and API calls

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/coffee-research-assistant.git
cd coffee-research-assistant
```

2. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows, use `.venv\Scripts\activate`
```

3. Install the required dependencies:
```bash
pip install -r requirements.txt
```

4. Copy the example environment file and configure your settings:
```bash
cp .env.example .env
```
Then edit `.env` with your DeepSeek API key and preferred settings.

## Usage

1. Start the application:
```bash
python scraper.py
```

2. Open your web browser and navigate to:
```
http://localhost:8000
```

3. Click the "Process New Paper Now" button to fetch and process your first paper, or wait for the daily scheduled job to run automatically at 8:00 AM.

## How It Works

### Paper Discovery
- Uses Google Scholar API through the Scholarly library to find recent coffee research
- Focuses on brewing techniques, extraction science, and practical applications
- Filters for relevant and impactful papers based on citations and content

### Processing Pipeline
1. Paper Discovery:
   - Searches Google Scholar for coffee brewing research
   - Extracts metadata (title, authors, year, citations)
   - Downloads available abstracts and content

2. Content Analysis:
   - Cleans and normalizes abstract text
   - Processes paper content for key findings
   - Identifies brewing-relevant information

3. AI Summary Generation:
   - Uses DeepSeek AI to generate concise summaries
   - Extracts practical brewing advice
   - Analyzes research impact on everyday coffee brewing

4. Data Storage:
   - Saves processed papers in JSON format
   - Maintains paper history
   - Enables quick retrieval and display

## Configuration

### Environment Variables
- `DEEPSEEK_API_KEY`: Your DeepSeek API key
- `PORT`: Server port (default: 8000)
- `HOST`: Server host (default: 0.0.0.0)
- `DAILY_UPDATE_TIME`: When to run daily updates (default: 08:00)
- `MAX_PAPERS_TO_KEEP`: Maximum papers to store (default: 50)

### Search Queries
Modify the `search_queries` list in `scraper.py` to customize paper discovery:
```python
search_queries = [
    "coffee brewing techniques",
    "coffee extraction science",
    "coffee brewing temperature",
    # Add your own queries here
]
```

## Development

### Project Structure
```
coffee-research-assistant/
├── scraper.py           # Main application file
├── requirements.txt     # Python dependencies
├── templates/           # HTML templates
│   ├── index.html      # Main page template
│   └── paper.html      # Individual paper template
├── static/             # Static assets
├── data/               # Stored paper data
└── docs/               # Documentation
```

### Running Tests
```bash
python -m pytest tests/
```

### Contributing
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## Troubleshooting

### Common Issues
1. **Google Scholar Rate Limiting**
   - Use a VPN or proxy
   - Reduce request frequency
   - Implement exponential backoff

2. **DeepSeek API Issues**
   - Verify API key
   - Check rate limits
   - Monitor response quality

3. **Server Won't Start**
   - Check port availability
   - Verify environment variables
   - Review log files

## License

MIT License - See [LICENSE](LICENSE) for details

## Acknowledgements

- [Scholarly](https://scholarly.readthedocs.io/) for academic paper search
- [DeepSeek AI](https://deepseek.ai/) for paper summarization
- [FastAPI](https://fastapi.tiangolo.com/) for the web framework
- [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/) for HTML parsing
- Coffee researchers worldwide for their valuable contributions

## Author

Your Name ([@yourusername](https://github.com/yourusername))

## Support

If you find this project helpful, please give it a ⭐! 