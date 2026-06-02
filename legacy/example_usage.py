#!/usr/bin/env python3
"""
Example usage of the CityHistoryGenerator class.
This script demonstrates how to use the generator programmatically.
"""

import os
from city_history_generator import CityHistoryGenerator

def example_basic_usage():
    """Example of basic usage with default cities."""
    print("🌍 Example 1: Basic Usage with Default Cities")
    print("=" * 50)
    
    # Initialize generator (will use environment variable or prompt for API key)
    try:
        generator = CityHistoryGenerator()
        
        # Generate histories for default cities
        histories = generator.generate_all_histories()
        
        # Print results
        generator.print_histories(histories)
        
        # Save to file
        generator.save_histories_to_file(histories, "example_default_cities.json")
        
    except ValueError as e:
        print(f"❌ Error: {e}")
        print("Please set your OpenAI API key first.")

def example_custom_cities():
    """Example with custom city list."""
    print("\n🌍 Example 2: Custom City List")
    print("=" * 50)
    
    # Custom list of European cities
    european_cities = [
        'Vienna', 'Prague', 'Budapest', 'Warsaw', 'Krakow'
    ]
    
    try:
        generator = CityHistoryGenerator()
        
        # Generate histories for custom cities
        histories = generator.generate_all_histories(european_cities)
        
        # Print results
        generator.print_histories(histories)
        
        # Save to file
        generator.save_histories_to_file(histories, "example_european_cities.json")
        
    except ValueError as e:
        print(f"❌ Error: {e}")
        print("Please set your OpenAI API key first.")

def example_single_city():
    """Example of generating history for a single city."""
    print("\n🌍 Example 3: Single City")
    print("=" * 50)
    
    try:
        generator = CityHistoryGenerator()
        
        # Generate history for one city
        city = "Venice"
        print(f"Generating history for {city}...")
        
        history_data = generator.generate_city_history(city)
        
        # Print the result
        print(f"\n🏙️  {history_data['city'].upper()}")
        print("-" * (len(history_data['city']) + 4))
        print(history_data['history'])
        print(f"\nGenerated: {history_data.get('generated_at', 'Unknown')}")
        
    except ValueError as e:
        print(f"❌ Error: {e}")
        print("Please set your OpenAI API key first.")

def example_with_api_key():
    """Example showing how to pass API key directly."""
    print("\n🌍 Example 4: Direct API Key Usage")
    print("=" * 50)
    
    # You can pass the API key directly (not recommended for production)
    api_key = os.getenv('OPENAI_API_KEY')
    
    if not api_key:
        print("⚠️  No API key found in environment variables.")
        print("This example requires OPENAI_API_KEY to be set.")
        return
    
    try:
        # Initialize with API key
        generator = CityHistoryGenerator(api_key=api_key)
        
        # Small list for demonstration
        small_cities = ['Amsterdam', 'Copenhagen']
        
        histories = generator.generate_all_histories(small_cities)
        generator.print_histories(histories)
        
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    """Run all examples."""
    print("🚀 City History Generator - Usage Examples")
    print("=" * 60)
    
    # Check if API key is available
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("⚠️  Warning: OPENAI_API_KEY environment variable not set.")
        print("Some examples may prompt for API key or fail.")
        print("Set it with: export OPENAI_API_KEY='your-api-key-here'")
        print()
    
    # Run examples
    example_basic_usage()
    example_custom_cities()
    example_single_city()
    example_with_api_key()
    
    print("\n🎉 All examples completed!")
    print("Check the generated JSON files for the results.")

if __name__ == "__main__":
    main() 