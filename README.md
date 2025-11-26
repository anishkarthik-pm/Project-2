# Groww App Review Analyzer

Automated weekly analysis of Groww app reviews from Google Play Store using AI-powered theme classification and summarization.

## Features

- **Automated Review Scraping**: Fetches latest reviews from Google Play Store
- **AI Theme Classification**: Uses Google Gemini API to categorize reviews into 10 predefined themes
- **Intelligent Summarization**: Generates concise weekly pulse notes highlighting key insights
- **Email Notifications**: Automatically drafts and sends stakeholder emails
- **PII Protection**: Removes personally identifiable information from all outputs
- **Scheduled Execution**: Runs every Monday at 9 AM IST via GitHub Actions

## Project Structure

```
groww-review-analyzer/
├── .github/workflows/      # GitHub Actions automation
├── src/                    # Source code modules
├── data/                   # Raw and processed review data
├── outputs/                # Generated notes and emails
├── logs/                   # Execution logs
├── prompts/                # AI prompt templates
├── tests/                  # Unit tests
├── main.py                 # Pipeline orchestrator
└── requirements.txt        # Python dependencies
```

## Setup Instructions

### Prerequisites

- Python 3.11 or higher
- Google Gemini API key
- Gmail account with app-specific password

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd groww-review-analyzer
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   ```

   Edit `.env` and add your credentials:
   - `GEMINI_API_KEY`: Your Google Gemini API key
   - `SMTP_USERNAME`: Your Gmail address
   - `SMTP_PASSWORD`: Your Gmail app-specific password
   - `EMAIL_TO`: Comma-separated recipient emails

### GitHub Actions Setup

1. **Add repository secrets** (Settings → Secrets → Actions):
   - `GEMINI_API_KEY`
   - `SMTP_USERNAME`
   - `SMTP_PASSWORD`
   - `EMAIL_FROM`
   - `EMAIL_TO`

2. **Enable GitHub Actions** in your repository settings

## Usage

### Local Execution

Run the complete pipeline:
```bash
python main.py
```

### Manual Rerun Instructions

If you need to rerun the analysis for a specific week:

1. **Set date range** (optional):
   Modify `WEEKS_LOOKBACK` in `.env` to change the analysis period

2. **Run pipeline**:
   ```bash
   python main.py
   ```

3. **Check outputs**:
   - Reviews: `data/raw/` and `data/processed/`
   - Weekly notes: `outputs/notes/`
   - Email drafts: `outputs/emails/`
   - Logs: `logs/pipeline.log`

### Running Individual Steps

```bash
# Step 1: Import reviews
python -m src.01_import_reviews

# Step 2: Classify themes
python -m src.02_classify_themes

# Step 3: Generate weekly note
python -m src.03_generate_note

# Step 4: Draft email
python -m src.04_draft_email

# Step 5: Send email
python -m src.05_send_email
```

### Scheduled Execution

The pipeline runs automatically every Monday at 9:00 AM IST via GitHub Actions.

**Manual trigger**:
1. Go to Actions tab in GitHub
2. Select "Weekly App Review Pulse"
3. Click "Run workflow"

## Testing

Run tests:
```bash
pytest tests/ -v
```

Run tests with coverage:
```bash
pytest tests/ --cov=src --cov-report=html
```

## Configuration

Key settings in `.env`:

| Variable | Description | Default |
|----------|-------------|---------|
| `WEEKS_LOOKBACK` | Number of weeks to analyze | 10 |
| `MAX_THEMES` | Maximum themes to track | 5 |
| `TOP_THEMES_FOR_REPORT` | Themes to include in reports | 3 |
| `WEEKLY_NOTE_MAX_WORDS` | Max words in weekly note | 250 |
| `EMAIL_DRAFT_MAX_WORDS` | Max words in email draft | 350 |
| `REVIEW_COUNT` | Max reviews to fetch | 500 |

## Output Formats

### Weekly Pulse Note (JSON)
```json
{
  "date_range": "2024-01-15 to 2024-01-21",
  "total_reviews": 150,
  "themes": {
    "UI/UX Issues": {"count": 45, "summary": "..."},
    "Performance Issues": {"count": 30, "summary": "..."}
  }
}
```

### Weekly Pulse Note (Markdown)
```markdown
📊 Weekly Review Pulse - Jan 15-21, 2024

Top Themes:
• **UI/UX Issues**: Users requesting dark mode...
• **Performance Issues**: App crashes on older devices...
```

### Email Draft (Text)
```
Hi team,

Here's this week's app review pulse...
```

## Theme Categories

1. UI/UX Issues
2. Performance Issues
3. Feature Requests
4. Account/Login Issues
5. Transaction Issues
6. Customer Support
7. Content/Data Issues
8. Security/Privacy Concerns
9. Positive Feedback
10. Other

## Privacy & Security

- **PII Removal**: All emails, phone numbers, and usernames are automatically scrubbed
- **Secure Credentials**: API keys and passwords stored in environment variables
- **No Data Retention**: Raw review data can be excluded from git (configured in .gitignore)

## Troubleshooting

**Pipeline fails to start:**
- Check all required environment variables are set
- Verify API credentials are valid

**Email not sending:**
- Ensure Gmail app-specific password is used (not regular password)
- Check SMTP settings and port (587 for TLS)

**Theme classification errors:**
- Verify Gemini API key has sufficient quota
- Check API rate limits

**GitHub Actions not running:**
- Verify repository secrets are configured
- Check workflow file syntax
- Ensure Actions are enabled in repository settings

## License

MIT License

## Support

For issues or questions, please open a GitHub issue.
