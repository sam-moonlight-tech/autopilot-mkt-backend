#!/usr/bin/env python3
"""Validate robot images in the database.

This script checks that all robots have image_url values set and that the URLs are valid.
"""

import sys
from pathlib import Path

# Add parent directory to path to import from src
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.supabase import get_supabase_client


def main() -> None:
    """Main execution function."""
    print("🔍 Validating robot images in database...\n")
    
    # Get Supabase client
    try:
        client = get_supabase_client()
    except Exception as e:
        print(f"❌ Error: Failed to initialize Supabase client: {e}")
        sys.exit(1)
    
    # Get all robots from database
    print("📋 Fetching robots from database...")
    try:
        robots_result = client.table("robot_catalog").select("id, name, image_url").execute()
        robots = robots_result.data or []
        print(f"✓ Found {len(robots)} robots in database\n")
    except Exception as e:
        print(f"❌ Error: Failed to fetch robots: {e}")
        sys.exit(1)
    
    # Validate each robot
    robots_with_images = 0
    robots_without_images = 0
    total_image_count = 0
    
    print("=" * 80)
    print(f"{'Robot Name':<30} {'Image URLs':<45} {'Count'}")
    print("=" * 80)
    
    for robot in robots:
        robot_name = robot.get("name", "Unknown")
        robot_id = robot.get("id", "")
        image_url = robot.get("image_url")
        
        if image_url:
            image_urls = [url.strip() for url in image_url.split(",") if url.strip()]
            robots_with_images += 1
            total_image_count += len(image_urls)
            
            # Display first URL (truncated) and count
            first_url = image_urls[0] if image_urls else ""
            display_url = first_url[:42] + "..." if len(first_url) > 45 else first_url
            print(f"{robot_name:<30} {display_url:<45} {len(image_urls)}")
            
            # Show additional URLs if multiple
            if len(image_urls) > 1:
                for url in image_urls[1:]:
                    display_url = url[:42] + "..." if len(url) > 45 else url
                    print(f"{'':30} {display_url:<45}")
        else:
            robots_without_images += 1
            print(f"{robot_name:<30} {'❌ NO IMAGES':<45} 0")
    
    print("=" * 80)
    print(f"\n📊 Summary:")
    print(f"   Total robots: {len(robots)}")
    print(f"   Robots with images: {robots_with_images}")
    print(f"   Robots without images: {robots_without_images}")
    print(f"   Total images: {total_image_count}")
    print(f"   Average images per robot: {total_image_count / robots_with_images if robots_with_images > 0 else 0:.1f}")
    
    # Sample a few URLs to verify they're accessible
    print(f"\n🔗 Testing image URLs accessibility...")
    if robots_with_images > 0:
        # Test first 3 robots with images
        import requests
        
        tested = 0
        accessible = 0
        for robot in robots:
            if tested >= 3:
                break
            image_url = robot.get("image_url")
            if image_url:
                first_url = image_url.split(",")[0].strip()
                try:
                    response = requests.head(first_url, timeout=5, allow_redirects=True)
                    if response.status_code == 200:
                        accessible += 1
                        print(f"   ✓ {robot.get('name', 'Unknown')}: Accessible (Status {response.status_code})")
                    else:
                        print(f"   ⚠️  {robot.get('name', 'Unknown')}: Status {response.status_code}")
                except Exception as e:
                    print(f"   ❌ {robot.get('name', 'Unknown')}: Error - {e}")
                tested += 1
        
        if tested > 0:
            print(f"\n   Tested {tested} URLs, {accessible} accessible")
    
    print("\n✅ Validation complete!")


if __name__ == "__main__":
    main()



