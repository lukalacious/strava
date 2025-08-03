<<<<<<< HEAD
# Strava Tell Me More 🚴‍♂️

A Python notebook that integrates with Strava API and OpenAI to generate engaging historical stories about your real cycling routes through Dutch cities and towns.

## Features

### 🚴‍♂️ Real Strava Integration
- Connects to your Strava account to fetch real cycling activities
- Extracts GPS route data from your actual rides
- Processes coordinates into location waypoints
- Falls back gracefully to mock data when Strava API is unavailable

### 🤖 AI-Powered Storytelling  
- Generates engaging historical narratives using OpenAI's GPT models
- Multiple story types: Dutch Golden Age, Modern, WWII Liberation themes
- Immersive storytelling that makes you feel like you were there
- Individual city summaries for deeper historical context

### 🔒 Security & Configuration
- Secure environment variable configuration for all API keys
- No hardcoded credentials in the notebook
- Template file for easy setup
- Comprehensive error handling throughout

### 📊 Smart Data Processing
- Modular architecture with separate classes for different functions
- GPS coordinate processing and location extraction
- Intelligent fallback systems for robustness
- JSON output with metadata for story archival

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Get API Keys:**
   
   **OpenAI API Key:**
   - Sign up at [OpenAI](https://platform.openai.com/)
   - Create an API key in your account settings
   
   **Strava API Credentials (optional but recommended):**
   - Go to [Strava API Settings](https://www.strava.com/settings/api)
   - Create a new application to get Client ID and Client Secret
   - Generate an access token for your account

3. **Configure Environment Variables:**
   ```bash
   # Copy the template file
   cp .env.template .env
   
   # Edit .env with your actual API keys
   OPENAI_API_KEY=your_openai_api_key_here
   STRAVA_CLIENT_ID=your_strava_client_id_here
   STRAVA_CLIENT_SECRET=your_strava_client_secret_here
   STRAVA_ACCESS_TOKEN=your_strava_access_token_here
   ```

## Usage

### Running the Notebook
1. **Start Jupyter:**
   ```bash
   jupyter notebook
   ```

2. **Open the notebook:**
   Navigate to `notebooks/strava_tell_me_more (strava-api).ipynb`

3. **Run all cells:**
   The notebook will automatically:
   - Connect to Strava API (if configured)
   - Fetch your recent cycling activities
   - Extract route waypoints from GPS data
   - Generate multiple types of historical stories
   - Save stories as JSON files

### Story Types Generated
- **Golden Age**: Experience your route as if cycling through 17th century Netherlands
- **Modern**: Contemporary cycling with historical context
- **War Liberation**: WWII liberation perspective (1944-1945)

## How It Works

### With Strava API
1. **Fetches Activities**: Retrieves your recent cycling activities
2. **Extracts GPS Data**: Gets coordinates from your actual routes  
3. **Processes Locations**: Converts GPS points to Dutch city/town names
4. **Generates Stories**: Creates historical narratives about your real routes

### Fallback Mode
If Strava API isn't configured, uses mock Dutch cycling route data:
- Segbroek, Kraayenstein, Kwintsheul, Schipluiden
- Berkel en Rodenrijs, Pijnacker, Leidschendam  
- Marlot, Haagse Bos

## Output

The notebook generates:
1. **Console Display**: Beautifully formatted stories with emojis and visual formatting
2. **JSON Files**: Individual story files for each narrative type
3. **Route Information**: Details about locations processed from your cycling data

### Sample Output Format
```json
{
  "story": "The cyclist embarked on their journey from the bustling city of...",
  "story_type": "golden_age",
  "generated_at": "2024-01-15T10:30:45.123456",
  "model_used": "gpt-3.5-turbo"
}
```

## Error Handling

The notebook handles various error scenarios gracefully:
- **Strava API Issues**: Falls back to mock data seamlessly
- **Authentication Errors**: Clear messages for invalid API keys  
- **Rate Limiting**: Handles OpenAI API rate limits
- **Network Problems**: Robust error handling with informative messages
- **Missing Dependencies**: Clear installation instructions

## Cost Considerations

- **OpenAI API**: Uses cost-effective GPT-3.5-turbo model
- **Token Limits**: 500-600 tokens per story (reasonable cost)
- **Strava API**: Free tier includes sufficient requests for personal use
- **Rate Limiting**: Built-in protections to avoid excessive API calls

## Architecture

### Key Components
- **StravaAPI**: Handles Strava authentication and data fetching
- **RouteProcessor**: Converts GPS coordinates to location names  
- **StoryGenerator**: Creates AI-powered historical narratives
- **Environment Configuration**: Secure API key management

## Requirements

- **Python 3.7+**
- **OpenAI API key** (required)
- **Strava API credentials** (optional, falls back to mock data)
- **Internet connection**
- **Jupyter Notebook** environment

## License

This project is open source and available under the MIT License.
